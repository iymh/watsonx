# req_wxai.py
from pydantic import BaseModel
import asyncio
from typing import AsyncGenerator, List, Optional

# LOG
import logging
# logging.basicConfig(format='[%(asctime)s] %(message)s', level=logging.DEBUG) # DEBUGレベルに設定
# logger = logging.getLogger("LOG")
# Chainlit側で設定されるため、ここでは設定しない方が良い場合がある
logger = logging.getLogger(__name__) # Chainlitに合わせて __name__ を使う

C_RED = '\033[31m'
C_RST = '\033[0m'
# logger.info(f"{C_RED}　no: {no}{C_RST}")

# env
import os
from dotenv import load_dotenv
load_dotenv()

# Langchain
from langchain_core.prompts import PromptTemplate

# ibm-watsonx-ai
from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models.utils.enums import ModelTypes, DecodingMethods
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames
from langchain_ibm import WatsonxLLM

api_key = os.getenv("API_KEY", None)
api_url = os.getenv("WML_URL", None)
creds = Credentials(url=api_url, api_key=api_key)
prj_id = os.getenv("WX_PRJID", None)


# print([model.name for model in ModelTypes])
# DEFAULT_MODEL = "meta-llama/llama-3-70b-instruct"
DEFAULT_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct-fp8"

# Parameters
class Params(BaseModel):
    modelname: str = DEFAULT_MODEL
    prompt: str = ""
    # stream: bool = False # LangChainのstream/astreamを使うので不要
    decoding_method: str = "greedy"
    min_new_tokens: int = 10
    max_new_tokens: int = 1024
    repetition_penalty: float = 1.1
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    stop_sequences: Optional[List[str]] = None


def setLlm(params: Params) -> WatsonxLLM:
    """
    指定されたパラメータに基づいて WatsonxLLM インスタンスを作成して返す関数。
    """
    logger.info(f"setLlm called with params: {params.dict(exclude={'prompt'})}")
    prms = {
        GenTextParamsMetaNames.DECODING_METHOD: params.decoding_method,
        GenTextParamsMetaNames.MAX_NEW_TOKENS: params.max_new_tokens,
        GenTextParamsMetaNames.MIN_NEW_TOKENS: params.min_new_tokens,
        GenTextParamsMetaNames.TEMPERATURE: params.temperature,
        GenTextParamsMetaNames.REPETITION_PENALTY: params.repetition_penalty,
        GenTextParamsMetaNames.TOP_K: params.top_k,
        GenTextParamsMetaNames.TOP_P: params.top_p,
        GenTextParamsMetaNames.STOP_SEQUENCES: params.stop_sequences
    }
    # None のパラメータを除外 (APIによってはエラーになるため)
    prms = {k: v for k, v in prms.items() if v is not None}
    logger.info(f"WatsonxLLM parameters: {C_RED}{prms}{C_RST}")

    llm = WatsonxLLM(
        model_id=params.modelname,
        url=creds["url"],
        apikey=creds["apikey"],
        project_id=prj_id,
        params=prms
    )
    logger.info(f"WatsonxLLM instance created for model: {params.modelname}")
    return llm

def setLlmChain(params: Params):
    """
    setLlm で LLM インスタンスを取得し、
    プロンプトテンプレートと結合した LangChain Chain (LCEL Runnable) を返す関数。
    """
    logger.info(f"setLlmChain called with params: {params.dict(exclude={'prompt'})}")
    # 1. LLMインスタンスを取得
    llm = setLlm(params)

    # 2. プロンプトテンプレートを定義 (CoT用)
    cot_template_string = """
以下の質問について、ステップバイステップで考え、最後に結論を日本語で答えてください。思考プロセスと結論は明確に区別してください。

思考プロセス開始:
[ここに思考プロセスを記述]
思考プロセス終了

結論:
[ここに最終的な結論を記述]

質問: {question}
"""
    # シンプルなテンプレート (CoTを使わない場合)
    # simple_template_string = "日本語で答えてください : {question}"

    ptemplate = PromptTemplate(
        input_variables=["question"],
        template=cot_template_string, # または simple_template_string
    )
    logger.info("PromptTemplate created.")

    # 3. プロンプトテンプレートとLLMを結合 (LCEL Runnable)
    lchain = ptemplate | llm
    logger.info("LCEL Runnable (Chain) created.")
    return lchain

# --- 既存の呼び出し関数 (修正不要の場合が多い) ---

def call_genai(params: Params):
    """
    同期的にLLM Chainを呼び出す関数 (主にテスト用)。
    """
    logger.info(f"call_genai: { params.dict(exclude={'prompt'}) }")
    logger.debug(f"Prompt: {params.prompt}")

    lchain = setLlmChain(params) # 修正後の関数を呼び出す
    ret = lchain.invoke({"question": params.prompt})
    logger.info(f"Result: {ret}")

    return ret

async def call_genai_stream(params: Params) -> AsyncGenerator[str, None]:
    """
    非同期でLLM Chainをストリーミング呼び出しする関数。
    """
    logger.info(f"call_genai_stream: { params.dict(exclude={'prompt'}) }")
    logger.debug(f"Prompt: {params.prompt}")

    lchain = setLlmChain(params) # 修正後の関数を呼び出す
    logger.debug("Start streaming...")
    async for chunk in lchain.astream({"question": params.prompt}): # astream を使う
        # logger.debug(f"Chunk: {chunk}") # デバッグログを有効にする場合
        yield chunk
        # await asyncio.sleep(0.001) # 通常は不要
    logger.debug("Streaming finished.")

# --- テスト用コード (必要に応じて) ---
async def _test():
    test_params = Params(
        prompt="IBM watsonxとは何ですか？簡単に説明してください。",
        max_new_tokens=150
    )
    # 同期呼び出しテスト
    # print("--- 同期呼び出しテスト ---")
    # result = call_genai(test_params)
    # print(f"同期結果:\n{result}")

    # 非同期ストリームテスト
    print("\n--- 非同期ストリームテスト ---")
    async for token in call_genai_stream(test_params):
        print(token, end="", flush=True)
    print("\n--- テスト完了 ---")

if __name__ == '__main__':
    # このファイル単体で実行した場合のテスト
    logging.basicConfig(level=logging.DEBUG) # テスト実行時のみDEBUGレベル設定
    asyncio.run(_test())
