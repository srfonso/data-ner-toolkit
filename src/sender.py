import re
import json
import time
import logging
import aiohttp
import asyncio
import os
from src.settings import (
    DEFAULT_BATCH_SIZE, 
    DEFAULT_MAX_PARALLEL_REQUESTS,
    DEFAULT_MAX_DATA_BY_REQUEST,
    DEFAULT_CHECKPOINT_FREQUENCY,
    DEFAULT_CHECKPOINT_FOLDER,
    MAX_TIMEOUT_SERVICES,
    DEFAULT_APIKEY
)
from src.models import GeneralEncoder, InputData, TextEntities, ResultData
from aiohttp.web_exceptions import HTTPException
from aiohttp.client_exceptions import ClientOSError, ClientResponseError, ContentTypeError


# Get an instance of a logger
logger = logging.getLogger(__name__)


async def async_session_cpm(service_url, session, data, bounded_info={}, default_return={}):
    """
    Asynchronous version using an existing session (to avoid creating a new one
    for each request). Creates a request to one of the REST API models for a prediction
    using an existing session.

    Parameters
    ----------
    service_url : str
        URL of the REST API model.

    session : aiohttp.ClientSession
        The aiohttp.ClientSession to be used for the request.

    data : str
        String with the request parameters (e.g., json.dumps).

    bounded_info : dict, optional
        Optional info to bind with the result.

    default_return : dict, optional
        Default return value in case of an error.

    Returns
    -------
    result : dict
        JSON result from the service request.
    """
    try:

        start_time = time.time()
        async with session.post(service_url, data=data, headers={"Accept": "application/json"}) as resp:
            result = await resp.json()
            elapsed = time.time() - start_time
            logger.debug(f"Request to {service_url} completed in {elapsed:.3f} secs. Status: {resp.status}")
            #result = {"result": extract_json(result["response"]), "model": result["model"]}
            if bounded_info:
                result.update(bounded_info)
            return result
    except ClientResponseError as e:
        logger.error(f"ClientResponseError: ({service_url}) {e.message} - {e.status}")
    except (asyncio.exceptions.TimeoutError, ClientOSError, ContentTypeError, HTTPException) as e:
        logger.error(f"{e.__class__.__name__}: ({service_url}) Error: {e}")
    return default_return


async def call_service(
    input_data: InputData, 
    lang: str,
    url: str, 
    max_parallel_requests: int = DEFAULT_MAX_PARALLEL_REQUESTS, 
    max_data_by_request: int = DEFAULT_MAX_DATA_BY_REQUEST,
    checkpoint_frequency: int = DEFAULT_CHECKPOINT_FREQUENCY, 
    checkpoint_folder: str = DEFAULT_CHECKPOINT_FOLDER, 
    results: ResultData = ResultData(),
    batch_size: int = DEFAULT_BATCH_SIZE, 
):
    """
    Send batched asynchronous requests to an external service and create checkpoints.

    Parameters
    ----------
    input_data : InputData
        Data model instance containing data to send and process.
    
    url : str
        The API endpoint URL.
    
    max_parallel_requests : int, default = DEFAULT_MAX_PARALLEL_REQUESTS
        Maximum number of parallel requests.

    max_data_by_request : int, default = DEFAULT_MAX_DATA_BY_REQUEST
        Maximum number of items sent in each request.

    checkpoint_frequency : int, default = DEFAULT_CHECKPOINT_FREQUENCY
        Number of items to process before creating a checkpoint.
    
    checkpoint_folder : str, default = DEFAULT_CHECKPOINT_FOLDER
        Folder where checkpoint JSON files are saved.
    
    results : ResultData, default = ResultData()
        List to store new results.

    batch_size : int, default=DEFAULT_BATCH_SIZE
        Number of requests per batch.        

    Returns
    -------
    results : ResultData
        Result Data model instance containing the already existing results.
    """
    timeout = aiohttp.ClientTimeout(total=MAX_TIMEOUT_SERVICES)
    checkpoint_index = 1
    next_checkpoint_threshold = checkpoint_frequency  # next threshold to trigger checkpoint
    
    # Pre-Build all request for API NER in order to subsequently correctly control its execution
    total_items = len(input_data.data)
    req_pool = []
    pre_build_items_pool = []
    for idx in range(0, total_items, max_data_by_request):
        pre_build_items = []
        texts_to_send = []
        # Chunk texts per request, create the same chunks for their IDs to enable tracking of responses.
        for text_item in input_data.data[idx:idx + max_data_by_request]:
            pre_build_items.append(TextEntities(ID=text_item.ID, subID=text_item.sub_ID))
            texts_to_send.append(text_item.text)

        # Add to pool
        pre_build_items_pool.append(pre_build_items)
        req_pool.append(
            {
                "lang": lang,
                # Split data in block of 'max_data_by_request' (to send in the same request)
                "data": texts_to_send,
                #"types": allowed_types
            }
        ) 

    # Ensure the checkpoint folder exists.
    if not os.path.exists(checkpoint_folder):
        os.makedirs(checkpoint_folder)
    
    # Global progress bar for overall processing.
    from tqdm import tqdm
    global_pbar = tqdm(total=total_items, desc="Processing", unit="item")
    
    for idx in range(0, len(req_pool), batch_size):
        batch_start_time = time.time()
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=max_parallel_requests),
            timeout=timeout,
            raise_for_status=True,
            headers={"Content-Type": "application/json", "ApiKey": DEFAULT_APIKEY}
        ) as session:
            tasks = [
                async_session_cpm(
                    service_url=url,
                    session=session,
                    data=json.dumps(payload),
                    bounded_info={},
                    default_return={
                        "results": []
                    }
                )
                for payload in req_pool[idx: idx + batch_size]
            ]
            # Run all tasks concurrently using gather.
            responses = await asyncio.gather(*tasks)
            # Synchronise IDs with the results
            counter = 0
            for r, pre_items_pool in zip(responses, pre_build_items_pool[idx: idx + batch_size]):
                counter += len(r["results"])
                for item_result, item in zip(r["results"], pre_items_pool):
                    item.entities=item_result["entities"]
                # Once items have been filled with entities, add into the results
                results.data.extend(pre_items_pool)
            global_pbar.update(counter)
        
        batch_elapsed = time.time() - batch_start_time
        logger.info(f"Batch {(idx//batch_size)+1}/{(len(req_pool)//batch_size) + 1} completed in {batch_elapsed:.3f} secs.")
        
        # If we've reached or exceeded the next checkpoint threshold, perform a checkpoint.
        results_counter = len(results.data)
        if results_counter >= next_checkpoint_threshold:
            # Remove previous checkpoint file if it exists.
            for filename in os.listdir(checkpoint_folder):
                if filename.startswith("checkpoint"):
                    os.remove(os.path.join(checkpoint_folder, filename))
                    break
            checkpoint_filename = os.path.join(
                checkpoint_folder,
                f"checkpoint_{checkpoint_index}_{results_counter}.json"
            )
            with open(checkpoint_filename, "w", encoding="utf-8") as f:
                json.dump(results.model_dump(), f, ensure_ascii=False, indent=2, cls=GeneralEncoder)
            logger.info(f"Checkpoint created: {checkpoint_filename} (Total items: {results_counter})")

            checkpoint_index += 1
            next_checkpoint_threshold += checkpoint_frequency

    global_pbar.close()
    return results
