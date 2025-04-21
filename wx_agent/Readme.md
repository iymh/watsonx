# watsonx.ai on pythonSDK

## purpose



## Python環境のセットアップ
```
# Set virtual environment
python -m venv .venv
source .venv/bin/activate
pip list


# Install the required modules
pip install -r requirements.txt

  or

# add python modules
pip install uvicorn fastapi python-dotenv langchain
#logging pandas

# add IBM SDK
pip install ibm-watsonx-ai langchain_ibm

 # pip install ibm-generative-ai
 # pip install ibm-watson

 # avoid exec error
  # packaging
```


## Run
* Run Server
  ```
  # chainlit run app_a.py -w -d
  ```
