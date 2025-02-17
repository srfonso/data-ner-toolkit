import os
import time
import json
import uuid
import sqlite3
import logging
import pandas as pd
from src.settings import DEFAULT_CHECKPOINT_FOLDER
from src.models import GeneralEncoder, InputData, ResultData

# Get an instance of a logger
logger = logging.getLogger(__name__)


def init_db(db_path: str = "executions.db") -> sqlite3.Connection:
    """ TODO
    Initialize the SQLite database and create the 'executions' table if it doesn't exist.
    The table uses a composite primary key (ID, sub_ID) where:
      - ID is the main identifier.
      - sub_ID is optional (defaults to 0 if not provided) and must be unique for the same ID.
    
    Parameters
    ----------
    db_path : str, default="executions.db"
        Path to the SQLite database file.
    
    Returns
    -------
    conn : sqlite3.Connection
        The connection object to the SQLite database.
    """
    # Connect to the SQLite database (it will be created if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the 'executions' table with a composite primary key (ID, sub_ID)
    # Note: sub_ID is defined as NOT NULL with a default value (0) to allow its optional nature at insertion time.
    create_table_query = """
        CREATE TABLE IF NOT EXISTS executions (
            ID TEXT NOT NULL,
            sub_ID INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (ID, sub_ID)
        );
    """
    cursor.execute(create_table_query)
    conn.commit()
    return conn


def save_result(results: ResultData, execution_folder: str):
    """
    Save the final result file with the accumulated results in the execution folder.
    This function first removes any older checkpoint files before saving the final result.

    Parameters
    ----------
    results : ResultData
        List of accumulated results.
    execution_folder : str
        Folder where the final result file will be saved.
    """
    # Remove any older checkpoint files.
    for filename in os.listdir(execution_folder):
        if filename.startswith("checkpoint_") and filename.endswith(".json"):
            file_path = os.path.join(execution_folder, filename)
            try:
                os.remove(file_path)
                logger.info(f"Removed old checkpoint file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")

    # Save the final result file.
    final_filename = os.path.join(execution_folder, "final_result.json")
    with open(final_filename, "w", encoding="utf-8") as f:
        json.dump(results.model_dump(), f, ensure_ascii=False, indent=2, cls=GeneralEncoder)
    logger.info(f"Final result saved: {final_filename}")


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
    execution_folder: str
        Path to the execution folder.
    """
    execution_folder = None
    for folder in os.listdir(base_folder):
        if folder.startswith(execution_id + "_") and os.path.isdir(os.path.join(base_folder, folder)):
            execution_folder = os.path.join(base_folder, folder)
            break
    if not execution_folder:
        logger.error(f"Execution folder for ID {execution_id} not found in {base_folder}.")
        exit(1)
        
    data_to_send_path = os.path.join(execution_folder, "data_to_send.json")
    if not os.path.exists(data_to_send_path):
        logger.error(f"data_to_send.json not found in {execution_folder}.")
        exit(1)
    
    with open(data_to_send_path, "r", encoding="utf-8") as f:
        # file structure -> {"data": [{}, {}...]}
        data_list = json.load(f)
    
    # Serialize the list of dictionaries into the custom InputData model
    data_to_send = InputData(**data_list)
    
    processed_ids = set()
    data_existing = ResultData()
    # Read already existing results from the first checkpoint file
    for filename in os.listdir(execution_folder):
        if filename.startswith("checkpoint"):
            filepath = os.path.join(execution_folder, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)
                data_existing = ResultData.model_validate(checkpoint_data)
                processed_ids = set([
                    f"{item.ID}_{item.subID}"
                    for item in data_existing.data
                    if item.entities  # checking if entities are not empty (request error)
                ])
            break  # only process the first checkpoint file found            
    return data_to_send, data_existing, processed_ids, execution_folder


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
    execution_folder : str
        Path to the execution folder.
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
    execution_folder = os.path.join(DEFAULT_CHECKPOINT_FOLDER, f"{execution_id}_{start_date}")
    os.makedirs(execution_folder, exist_ok=True)
    
    print(f"New Execution ID: {execution_id}")
    logger.info(f"New execution folder created: {execution_folder}")
    
    data_to_send_path = os.path.join(execution_folder, "data_to_send.json")
    with open(data_to_send_path, "w", encoding="utf-8") as f:
        # file structure -> {"data": [{}, {}...]}
        json.dump(data_model.model_dump(), f, ensure_ascii=False, indent=2, cls=GeneralEncoder)
    logger.info(f"data_to_send.json saved in {execution_folder}")
    
    # Return the InputData model instance and the execution folder.
    return data_model, execution_folder


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
    execution_folder : str
        Path to the execution folder.
    """
    data_to_send, data_existing, processed_ids, execution_folder = load_existing_execution(args.execution_id)
    
    logger.info(f"Resuming execution '{args.execution_id}' from folder: {execution_folder}")
    
    # data_to_send is an InputData model instance; iterate over its list of TextItem.
    data_remaining = InputData(
        data=[
            item for item in data_to_send.data
            if f"{item.ID}_{item.sub_ID}" not in processed_ids
        ]
    )
    if not data_remaining.data:
        logger.info("All items have been processed. Nothing to do.")
        exit(0)
    return data_remaining, data_existing, execution_folder