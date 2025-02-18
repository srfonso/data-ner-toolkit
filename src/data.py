import os
import time
import json
import uuid
import shutil
import pandas as pd
from src.logs import setup_logging
from src.settings import DEFAULT_CHECKPOINT_FOLDER, DEFAULT_RESULT_FOLDER
from src.models import GeneralEncoder, InputData, ResultData


# Get an instance of a logger
logger = setup_logging(__name__)


def save_final_result(
    results: ResultData, 
    checkpoint_folderpath: str
):
    """
    Save the final result file with the accumulated results in the execution folder.
    This function first removes any older checkpoint files before saving the final result.

    Parameters
    ----------
    results: ResultData
        List of accumulated results.
    checkpoint_folderpath : str
        Folder where the checkpoints data is stored.
    """

    # Get result path from checkpoint folder
    result_folderpath = os.path.join(
        DEFAULT_RESULT_FOLDER, 
        os.path.basename(checkpoint_folderpath)
    )

    # Ensure the checkpoint folder exists.
    if not os.path.exists(result_folderpath):
        os.makedirs(result_folderpath)

    # First: Save the final result file.
    final_filename = os.path.join(result_folderpath, "final_result.json")
    with open(final_filename, "w", encoding="utf-8") as f:
        json.dump(results.model_dump(), f, ensure_ascii=False, indent=2, cls=GeneralEncoder)

    # Then: Remove checkpoint folder.
    if os.path.exists(checkpoint_folderpath):
        shutil.rmtree(checkpoint_folderpath)
        logger.debug(f"Checkpoint folder `{checkpoint_folderpath}` and its contents have been removed.")

    logger.info(f"Final result saved: {final_filename}")


def save_checkpoint(results: ResultData, checkpoint_folderpath: str):
    """
    Save the final result file with the accumulated results in the execution folder.
    This function first removes any older checkpoint files before saving the final result.

    Parameters
    ----------
    results: ResultData
        List of accumulated results.
    checkpoint_folder: str
        Folder where the checkpoint file will be saved.
    """
    # Ensure the checkpoint folder exists.
    if not os.path.exists(checkpoint_folderpath):
        os.makedirs(checkpoint_folderpath)

    # Remove previous checkpoint file if it exists.
    for filename in os.listdir(checkpoint_folderpath):
        if filename.startswith("checkpoint"):
            os.remove(os.path.join(checkpoint_folderpath, filename))
            break
    checkpoint_filename = os.path.join(
        checkpoint_folderpath,
        f"checkpoint_{len(results.data)}.json"
    )
    with open(checkpoint_filename, "w", encoding="utf-8") as f:
        json.dump(results.model_dump(), f, ensure_ascii=False, indent=2, cls=GeneralEncoder)
    logger.info(f"Checkpoint created: {checkpoint_filename} (Total items: {len(results.data)})")


def read_csv_and_generate_data(
    csv_file: str, 
    id_column: str, 
    text_column: str, 
    sub_id_column: str = None, 
    max_items: int = None
) -> InputData:
    """
    Read the CSV file, extract intervention IDs and texts from the specified columns,
    clean and split the texts into phrases, and generate a list of dictionaries.

    Parameters
    ----------
    csv_file : str
        Path to the CSV file.
    id_column : str
        Column name that contains the primary IDs.
    text_column : str
        Column name that contains the texts.
    sub_id_column: str, default = None
        Column name that contains an optional sub id.
    max_items : int, default = None
        Maximum number of items to process. If None, all rows are processed.

    Returns
    -------
    data_model : InputData
        A InputData model instance containing a list of TextItem.
    """
    df = pd.read_csv(csv_file)
    df = df[:max_items] if max_items is not None else df

    # Columns to extract and rename
    columns_to_select = [id_column, text_column]
    rename_mapping = {
        id_column: "ID", 
        text_column: "text"
    }

    # If a sub_ID is given, it is added to the columns for extracting
    if sub_id_column is not None:
        columns_to_select.append(sub_id_column)
        rename_mapping[sub_id_column] = "sub_ID"

    df_filtered = df[columns_to_select].rename(
        columns=rename_mapping
    )
    data_list = df_filtered.to_dict(orient="records")
    
    # Create and return a Data model instance
    return InputData(data=data_list)


def load_existing_execution(
    execution_id: str, 
    base_folder: str = DEFAULT_CHECKPOINT_FOLDER
) -> tuple[InputData, ResultData, set, str]:
    """
    Load data_to_send.json and already processed intervention IDs from an existing execution folder.

    Parameters
    ----------
    execution_id: str
        Execution ID to resume.
    base_folder: str, default=DEFAULT_CHECKPOINT_FOLDER
        Checkpoint base folder.

    Returns
    -------
    data_to_send: InputData
        Data model instance containing the data from `data_to_send.json`.
    data_existing: ResultData
        Result Data model instance containing the already existing results.
    processed_ids: set
        Set of IDs that have been processed successfully.
    checkpoint_folderpath: str
        Path to the execution folder.
    """
    checkpoint_folderpath = None
    for folder in os.listdir(base_folder):
        if folder.startswith(execution_id + "_") and os.path.isdir(os.path.join(base_folder, folder)):
            checkpoint_folderpath = os.path.join(base_folder, folder)
            break
    if not checkpoint_folderpath:
        logger.error(f"Execution folder for ID {execution_id} not found in {base_folder}.")
        exit(1)
        
    data_to_send_path = os.path.join(checkpoint_folderpath, "data_to_send.json")
    if not os.path.exists(data_to_send_path):
        logger.error(f"data_to_send.json not found in {checkpoint_folderpath}.")
        exit(1)
    
    with open(data_to_send_path, "r", encoding="utf-8") as f:
        # file structure -> {"data": [{}, {}...]}
        data_list = json.load(f)
    
    # Serialize the list of dictionaries into the custom InputData model
    data_to_send = InputData(**data_list)
    
    processed_ids = set()
    data_existing = ResultData()
    # Read already existing results from the first checkpoint file
    for filename in os.listdir(checkpoint_folderpath):
        if filename.startswith("checkpoint"):
            filepath = os.path.join(checkpoint_folderpath, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)
                data_existing = ResultData.model_validate(checkpoint_data)
                processed_ids = set([
                    f"{item.ID}_{item.subID}"
                    for item in data_existing.data
                ])
            break  # only process the first checkpoint file found            
    return data_to_send, data_existing, processed_ids, checkpoint_folderpath


def prepare_new_execution(args):
    """
    Prepare a new execution from a CSV file.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command-line arguments.

    Returns
    -------
    data_model : InputData
        InputData model instance containing payloads.
    checkpoint_folderpath : str
        Path to the checkpoint folder.
    """
    data_model = read_csv_and_generate_data(
        csv_file=args.csv, 
        id_column=args.id_column, 
        text_column=args.text_column, 
        sub_id_column=args.sub_id, 
        max_items=args.n_items
    )
    
    if not data_model.data:
        logger.error("No valid data found in CSV.")
        exit(1)
    
    execution_id = uuid.uuid4().hex
    start_date = time.strftime("%Y%m%d_%H%M%S")
    checkpoint_folderpath = os.path.join(DEFAULT_CHECKPOINT_FOLDER, f"{execution_id}_{start_date}")
    os.makedirs(checkpoint_folderpath, exist_ok=True)
    
    print(f"New Execution ID: {execution_id}")
    logger.info(f"New execution folder created: {checkpoint_folderpath}")
    
    data_to_send_path = os.path.join(checkpoint_folderpath, "data_to_send.json")
    with open(data_to_send_path, "w", encoding="utf-8") as f:
        # file structure -> {"data": [{}, {}...]}
        json.dump(data_model.model_dump(), f, ensure_ascii=False, indent=2, cls=GeneralEncoder)
    logger.info(f"data_to_send.json saved in {checkpoint_folderpath}")
    
    # Return the InputData model instance and the execution folder.
    return data_model, checkpoint_folderpath


def prepare_resume_execution(args) -> tuple[InputData, ResultData, str]:
    """
    Prepare resuming an execution from a previous run.

    Parameters
    ----------
    args: argparse.Namespace
        Parsed command-line arguments.

    Returns
    -------
    data_remaining: InputData
        Data model instance containing remaining data to be processed.
    data_existing: ResultData
        Result Data model instance containing the already existing results.
    checkpoint_folderpath : str
        Path to the checkpoint folder.
    """
    data_to_send, data_existing, processed_ids, checkpoint_folderpath = load_existing_execution(args.execution_id)
    
    logger.info(f"Resuming execution '{args.execution_id}' from folder: {checkpoint_folderpath}")
    
    # data_to_send is an InputData model instance; iterate over its list of TextItem.
    data_remaining = InputData(
        data=[
            item for item in data_to_send.data
            if f"{item.ID}_{item.sub_ID}" not in processed_ids
        ]
    )
    return data_remaining, data_existing, checkpoint_folderpath