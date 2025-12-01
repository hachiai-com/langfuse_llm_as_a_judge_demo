# langfuse_llm_as_a_judge_demo

Start LangFuse services:
   ```
   docker compose up -d 
   ```
Run the application:
   ```
   docker compose run app python main.py
   ```
Or if the container is already running:
  ```   
   docker compose exec app python main.py
  ```
Option 2: Running locally (without Docker)
    
    Create and activate a virtual environment:
    python -m venv venv   
    
    # On Windows:   
    venv\Scripts\activate   
    
    # On Mac/Linux:   
    source venv/bin/activate
    
    Install dependencies:
    pip install -r requirements.txt
    
    Start LangFuse with Docker (still needed for the LangFuse server):
    docker compose up -d
    
    Run the application:
    python main.py
