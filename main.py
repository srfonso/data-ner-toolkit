import os
import time
import argparse
import asyncio
import logging
from src.models import ResultData
from src.sender import call_service
from src.data import (
    prepare_new_execution,
    prepare_resume_execution,
    save_result
)
from src.settings import (
    DEFAULT_ENDPOINT,
    DEFAULT_MAX_PARALLEL_REQUESTS,
    DEFAULT_CHECKPOINT_FREQUENCY,
    LOG_DIR,
)


# Logger configuration (using LOG_DIR from settings.py)
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
log_file = os.path.join(LOG_DIR, "file.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)


# Get an instance of a logger
logger = logging.getLogger(__name__)


def parse_args():
    """
    Parse command-line arguments for the LLM tool using subparsers for
    separate "new" and "resume" commands.

    Returns
    -------
    args : argparse.Namespace
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Tool to interact with Ollama LLM."
    )
    # General arguments shared by both commands.
    group_g = parser.add_argument_group("General arguments")
    group_g.add_argument(
        "-L", "--loglevel", 
        dest="log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logger level. (default: INFO)"
    )
    group_g.add_argument(
        "--url",
        type=str,
        default=DEFAULT_ENDPOINT,
        help=f"API endpoint URL. (default: {DEFAULT_ENDPOINT})"
    )
    group_g.add_argument(
        "--max_parallel_requests",
        type=int,
        default=DEFAULT_MAX_PARALLEL_REQUESTS,
        help=f"Maximum number of parallel requests. (default: {DEFAULT_MAX_PARALLEL_REQUESTS})"
    )
    group_g.add_argument(
        "--checkpoint_frequency",
        type=int,
        default=DEFAULT_CHECKPOINT_FREQUENCY,
        help=f"Number of items per checkpoint. (default: {DEFAULT_CHECKPOINT_FREQUENCY})"
    )
    group_g.add_argument(
        "--n_items",
        type=int,
        default=None,
        help="Total number of items to process (only used for new executions). Default: None (all items)."
    )

    # Create subparsers for the two execution modes.
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for new execution (CSV provided)
    new_parser = subparsers.add_parser(
        "new",
        help="New execution using CSV"
    )
    new_parser.add_argument(
        "--csv",
        type=str,
        required=True,
        help="CSV file containing texts for new execution. (required)"
    )
    new_parser.add_argument(
        "--lang",
        type=str,
        required=True,
        help=f"Language ISO-639-1 code of the dataset."
    )
    new_parser.add_argument(
        "--text_column",
        type=str,
        required=True,
        help="Name of the CSV column that contains the chunked texts. (required)"
    )
    new_parser.add_argument(
        "--id_column",
        type=str,
        required=True,
        help="Name of the CSV column that contains the intervention IDs. (required)"
    )
    new_parser.add_argument(
        "--sub_id",
        type=str,
        required=False,
        help="Name of the CSV column that contains a sub ID. (optional)"
    )

    # Subparser for resuming a previous execution
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a previous execution"
    )
    resume_parser.add_argument(
        "--lang",
        type=str,
        required=True,
        help=f"Language ISO-639-1 code of the dataset."
    )
    resume_parser.add_argument(
        "--execution_id",
        type=str,
        required=True,
        help="Execution ID of a previous run to resume. (required)"
    )

    return parser.parse_args()

async def main():
    """
    Main asynchronous function to execute service calls, handle checkpoints,
    and manage the overall execution flow.
    """
    args = parse_args()
    numeric_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    
    # Determine execution mode: new execution (CSV provided) or resume (execution_id provided)
    if args.command == "new":
        data_remaining, execution_folder = prepare_new_execution(args)
        data_existing = ResultData()
    else:
        data_remaining, data_existing, execution_folder = prepare_resume_execution(args)
    
    start_time = time.time()
    results = await call_service(
        input_data=data_remaining,
        lang=args.lang,
        url=args.url,
        max_parallel_requests=args.max_parallel_requests,
        checkpoint_frequency=args.checkpoint_frequency,
        checkpoint_folder=execution_folder,
        results=data_existing
    )
    results = []
    total_time = time.time() - start_time
    logger.info(f"Processing completed in {total_time:.3f} secs.")
    if results:
        save_result(results, execution_folder)
    
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting gracefully.")
