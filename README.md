# data-ner-toolkit

**data-ner-toolkit** is a versatile, out-of-the-box, and easy-to-deploy tool for performing Named Entity Recognition (NER) on any dataset. Its modular design allows you to:

- Easily process CSV files.
- Perform **checkpoints** to pause and resume (`resume`) when needed.
- Deploy a scalable NER microservice (via load balancing).
- Customize models and settings to your needs.


Developed by the [Cybersecurity and Privacy Protection Research Group (GiCP)](https://gicp.es)

---

## Table of Contents

- [Key Features](#key-features)
- [Checkpoints and Resuming](#checkpoints-and-resuming)
- [General Architecture](#general-architecture)
- [Installation](#installation)
- [CLI Usage](#cli-usage)
  - [Subcommand `new`](#subcommand-new)
  - [Subcommand `resume`](#subcommand-resume)
- [The `api_ner` Microservice](#the-apiner-microservice)
  - [Configuration](#configuration)
  - [Deployment with Docker Compose](#deployment-with-docker-compose)
- [Output Structure](#output-structure)
- [Example Workflow](#example-workflow)
- [Customization](#customization)
- [License](#license)

---

## Key Features

- **CLI** (`ner.py`) to execute NER tasks:
  - **Subcommand** `new`: start a new run from a CSV file.
  - **Subcommand** `resume`: resume a previous run that was interrupted.
- **Microservice** (`api_ner`) based on _FastAPI_:
  - Receives text requests and returns recognized entities.
  - Can be easily scaled using _Traefik_ as a load balancer.
- **Checkpoints** to pause and resume the process without losing progress.
- **Compatible** with different NER models (default uses _spaCy_ in Spanish and English).
- **Advanced settings** to customize behavior (parallel requests, batch size, timeouts, etc.).
- **"sub-ID" support** for handling text chunks or partial segments belonging to the same main ID.

---

## Checkpoints and Resuming

The tool generates **checkpoints** in the folder configured by `DEFAULT_CHECKPOINT_FOLDER = ".checkpoints"` after reaching the defined frequency (`--checkpoint_frequency` or `DEFAULT_CHECKPOINT_FREQUENCY` in `settings.py`).

- **Reason**: to pause the run (or in case it stops unexpectedly) and later resume without having to reprocess everything.
- At the end of the entire process (when all data has been processed), a final output file is placed in the `results/` folder (or whichever is defined in `settings.py`). The run is considered complete only when **no pending data** remains.

---

## General Architecture

```
                +-------------------+
                |   data-ner-tool   | (CLI)
                +---------+---------+
                        |   ^
                        v   |
     +-----------------------------------------+
     | Traefik (Load Balancer & Reverse Proxy) |
     +-----------------------------------------+
             / \                       / \
            /   \                     /   \
    +-------------------+     +-------------------+
    |   API Endpoint    | ... |   API Endpoint    |   (FastAPI: api_ner)
    +-------------------+     +-------------------+
``` 

1. The **CLI** (`ner.py`) reads from a CSV file.
2. It sends texts to the **`api_ner` microservice**.
3. The microservice, via _Traefik_, can be replicated in multiple containers to increase processing capacity.
4. Results are stored incrementally in **checkpoints** until the final output is generated.

---

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/srfonso/data-ner-toolkit.git
   cd data-ner-toolkit
   ```
2. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv venv
   . venv/bin/activate  
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Deploy microservice [Check here](#deployment-with-docker-compose). And add into the `src/settings` the right URL. 
---

## CLI Usage

Use the following to see the general help:

```bash
python ner.py --help
```

The tool provides two main subcommands: `new` and `resume`.

### Subcommand `new`

Starts a **new run** using a CSV file.  
Example:

```bash
python ner.py new \
  --lang es \
  --csv /path/to/myfile.csv \
  --text_column text \
  --id_column ID \
  --sub_id chunk_id
```

**Key parameters**:
- `--csv CSV`: Path to the input CSV file. *(Required)*
- `--lang LANG`: ISO-639-1 language code (e.g., `es`, `en`). *(Optional; defaults to `es` if configured so)*
- `--text_column TEXT_COLUMN`: Name of the column that contains the text or chunk. *(Required)*
- `--id_column ID_COLUMN`: Name of the column containing the unique intervention (or document) ID. *(Required)*
- `--sub_id SUB_ID`: A sub-identifier column (e.g., for chunks). *(Optional)*

**Complete example**:
```bash
python ner.py new \
  --lang es \
  --csv data/chunks_output.csv \
  --text_column chunk \
  --id_column ID \
  --sub_id chunk_id \
  --max_parallel_requests 8 \
  --checkpoint_frequency 5000
```

### Subcommand `resume`

Resumes a previous run that was paused or interrupted:
```bash
python ner.py resume \
  --lang es \
  --execution_id 123e4567-e89b-12d3-a456-426614174000
```

- `--execution_id EXECUTION_ID`: The run ID assigned during the previous run. *(Required)*
- `--lang LANG`: Specifies the language. *(Optional, but recommended to match the original run)*

---

## The `api_ner` Microservice

This microservice, built with _FastAPI_, exposes an endpoint to process text and return named entities.  
The default _spaCy_ models are:
- Spanish: `es_core_news_lg`
- English: `en_core_web_lg`

### Configuration

In `api_ner/settings.py` you will find:
```python
ALLOWED_LANG_MODELS = {
    "es": ("es_core_news_lg", []),
    "en": ("en_core_web_lg", []),
    # Add more languages/models as needed
}
```
To add a new model, you only need to:
1. Install that model in the container or environment.
2. Add it to `ALLOWED_LANG_MODELS`.
3. Update `api_ner/download.sh` to automatically download it during the image build process.

### Deployment with Docker Compose

To deploy the microservice just use the following command:
```bash
docker-compose -p data-ner-tool up -d --scale ner-api=2
```
- `-p data-ner-tool`: The name of the _docker-compose_ project.
- `--scale ner-api=2`: Launches 2 containers of the microservice for load balancing.

---

## Output Structure

The final NER results are stored in a data model like this:

```python
class Entity(BaseModel):
    name: str
    type: str
    start_offset: int
    end_offset: int

class TextEntities(BaseModel):
    ID: uuid.UUID
    subID: int
    entities: list[Entity] = Field(default_factory=list)

class ResultData(BaseModel):
    data: list[TextEntities] = Field(default_factory=list)
```

Each CSV row is transformed into a `TextEntities`, with:
- `ID`: Main identifier.
- `subID`: Sub-identifier (if applicable).
- `entities`: List of detected entities. Each `Entity` contains:
  - `name`: The textual surface form of the entity.
  - `type`: The entity type (PERSON, ORG, LOC, etc.).
  - `start_offset` / `end_offset`: Character positions in the original text.

The final result (once all data is processed) is placed under the `results/` folder.

> **Note**: You can customize or replace the microservice as long as the API returns data in the same structure as shown above. This ensures compatibility with the data models defined in `src/models.py`.

---

## Example Workflow

1. **Prepare your CSV**  
   Suppose you have a CSV file `data/chunks_output.csv` with columns:
   - `ID`: Identifies the intervention or document.
   - `chunk_id`: A sub-identifier.
   - `chunk`: The actual text to process.
   
2. **Start a new run**  
   ```bash
   python ner.py new \
     --lang es \
     --csv data/chunks_output.csv \
     --text_column chunk \
     --id_column ID \
     --sub_id chunk_id
   ```
   - **Checkpoints** will be created every 10,000 items by default (or the frequency you specify).

3. **Pause / Resume**  
   - If the process stops for any reason, note the `execution_id` shown in the console.
   - To resume:
     ```bash
     python ner.py resume \
       --lang es \
       --execution_id <YOUR_EXECUTION_ID>
     ```
4. **Check the results**  
   - Once completed, the final output file can be found in `./results/`.

---

## Customization

You can modify many settings in `settings.py`:

```python
MAX_TIMEOUT_SERVICES = 1800
DEFAULT_ENDPOINT = "http://ner.localhost:65430/ner"
DEFAULT_APIKEY_HEADER = "ApiKey"
DEFAULT_APIKEY = "..."
DEFAULT_MAX_DATA_BY_REQUEST = 500
DEFAULT_MAX_PARALLEL_REQUESTS = 4  # (Num workers * Num containers)
DEFAULT_BATCH_SIZE = 5
DEFAULT_CHECKPOINT_FREQUENCY = 10000
DEFAULT_CHECKPOINT_FOLDER = ".checkpoints"
DEFAULT_RESULT_FOLDER = "results"
LOG_DIR = ".logs"
```

- **`MAX_TIMEOUT_SERVICES`**: Maximum wait time (in seconds) for requests to the NER service.
- **`DEFAULT_MAX_PARALLEL_REQUESTS`**: Maximum number of concurrent requests.
- **`DEFAULT_CHECKPOINT_FREQUENCY`**: After how many items to create a checkpoint.
- **`DEFAULT_BATCH_SIZE`**: The size of the batch of texts sent per request.
- **`LOG_DIR`**: Folder to store logs.

**Microservice** `api_ner`:
- Edit/add models in `api_ner/settings.py`:
  ```python
  ALLOWED_LANG_MODELS = {
      "es": ("es_core_news_lg", []),
      "en": ("en_core_web_lg", []),
      "fr": ("fr_core_news_lg", [])  # Example for French
  }
  ```
- Update the `api_ner/download.sh` to automatically install the new model when building the image.

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).  
Please see the [LICENSE](LICENSE) file for more details.