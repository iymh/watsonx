# app_a_cot.py (ファイル名を変更して保存することを推奨)
import chainlit as cl
import asyncio
from dotenv import load_dotenv
import os
import logging

# LangChain Core (PromptTemplate) とコールバック関連
from langchain_core.prompts import PromptTemplate
from langchain.callbacks.base import AsyncCallbackHandler
from langchain_core.outputs import LLMResult
from typing import Any, Dict, List, Optional, Union

# 提供された req_wxai モジュールをインポート
try:
    import req_wxai as GEN
except ImportError:
    print("エラー: req_wxai.py が見つかりません。app_a_cot.py と同じディレクトリに配置してください。")
    exit()

# LOG設定
logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


# .env ファイルから環境変数を読み込む
load_dotenv()

# --- トークン数集計用カスタムコールバックハンドラ ---
class TokenUsageCallbackHandler(AsyncCallbackHandler):
    """LLM呼び出しのトークン数を集計するコールバックハンドラ"""
    def __init__(self):
        super().__init__()
        self.total_input_tokens = 0
        self.total_generated_tokens = 0

    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        pass

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM呼び出し終了時にトークン数を集計"""
        if response.llm_output is None or "token_usage" not in response.llm_output:
            logger.warning("コールバック: llm_output または token_usage が見つかりません。")
            return

        token_usage = response.llm_output["token_usage"]
        logger.debug(f"コールバック: token_usage: {token_usage}")

        input_tokens = token_usage.get("prompt_tokens")
        generated_tokens = token_usage.get("completion_tokens")

        # watsonx.ai の場合のキー名 (要確認)
        if input_tokens is None:
            input_tokens = token_usage.get("input_token_count")
        if generated_tokens is None:
            generated_tokens = token_usage.get("generated_token_count")

        if input_tokens is not None and generated_tokens is not None:
            logger.info(f"コールバック: LLM Token Usage: Input={input_tokens}, Generated={generated_tokens}")
            self.total_input_tokens += int(input_tokens)
            self.total_generated_tokens += int(generated_tokens)
        else:
            logger.warning(f"コールバック: トークン数情報が見つかりません in token_usage: {token_usage}")

    def get_total_tokens(self) -> Dict[str, int]:
        """集計したトークン数を返す"""
        return {
            "input": self.total_input_tokens,
            "generated": self.total_generated_tokens,
            "total": self.total_input_tokens + self.total_generated_tokens,
        }

# --- Chainlit アプリケーション ---
@cl.on_chat_start
async def start_chat():
    """
    チャットセッション開始時に呼び出される関数 (CoT usecase 用)。
    LLMチェーンを初期化し、ユーザーセッションに保存します。
    """
    logger.info("チャットセッション開始 (CoT usecase)")
    try:
        # デフォルトのパラメータでLLMチェーンを設定
        # CoTは長くなる可能性があるので max_new_tokens を調整
        params = GEN.Params(
            max_new_tokens=1024,
            # stop_sequences=['<|eot_id|>','<|end_of_text|>']
            stop_sequences=["<|eot_id|>"]
        )
        logger.info(f"使用モデル: {params.modelname}, パラメータ: {params.dict(exclude={'prompt'})}")

        # req_wxai.py の setLlmChain を使用してLangChainオブジェクトを取得
        # ★ 注意: setLlmChain 内のプロンプトテンプレートがCoT用に設定されていることを確認
        # (例: 思考プロセス開始/終了、結論タグを含むテンプレート)
        # もし req_wxai.py がCoT用でない場合、ここで上書きが必要
        # --- CoTプロンプトテンプレートをここで定義する場合 ---
        llm = GEN.setLlm(params) # LLMインスタンスを取得
        cot_template_string = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
あなたは役立つAIアシスタントです。以下の質問について、ステップバイステップで考え、最後に結論を日本語で答えてください。思考プロセスと結論は明確に区別してください。

思考プロセス開始:
[ここに思考プロセスを記述]
思考プロセス終了

結論:
[ここに最終的な結論を記述]
<|eot_id|><|start_header_id|>user<|end_header_id|>

質問: {question}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        ptemplate = PromptTemplate(
            input_variables=["question"],
            template=cot_template_string,
        )
        lchain = ptemplate | llm
        # ---------------------------------------------
        # req_wxai.py の setLlmChain をそのまま使う場合 (CoT用テンプレートが設定されている前提)
        # lchain = GEN.setLlmChain(params)

        # LLMチェーンとパラメータをユーザーセッションに保存
        cl.user_session.set("llm_chain", lchain)
        cl.user_session.set("llm_params", params)

        await cl.Message(
            content=f"こんにちは！ **{params.modelname}** を使って思考プロセスを含めて応答します。質問を入力してください。"
        ).send()
        logger.info("LLMチェーンの初期化完了")

    except Exception as e:
        logger.error(f"初期化エラー: {e}", exc_info=True)
        await cl.ErrorMessage(
            content=f"チャットの初期化中にエラーが発生しました: {e}\n環境変数（API_KEY, WML_URL, WX_PRJID）が正しく設定されているか確認してください。"
        ).send()


############ CoT　usecase
@cl.on_message
async def main(message: cl.Message):
    """
    ユーザーからのメッセージ受信時に呼び出される関数 (CoT usecase)。
    LLMを呼び出し、応答をパースして思考プロセスと結論を表示します。
    トークン数もカウントします。
    """
    lchain = cl.user_session.get("llm_chain")
    if not lchain:
        await cl.ErrorMessage(content="エラー: LLMチェーンが初期化されていません。ページをリロードしてください。").send()
        return

    user_query = message.content
    logger.info(f"受信メッセージ: {user_query}")

    # カスタムコールバックハンドラのインスタンスを作成
    token_handler = TokenUsageCallbackHandler()

    try:
        logger.info("LLM呼び出し開始 (CoT - ainvoke)")
        # ainvoke にコールバックハンドラを指定
        raw_response = await lchain.ainvoke(
            {"question": user_query},
            config={"callbacks": [token_handler]} # コールバックを指定
        )

        # Remove Llama end tag.
        full_response = raw_response
        stop_token = "<|eot_id|>"
        if isinstance(raw_response, str) and raw_response.endswith(stop_token):
            full_response = raw_response[:-len(stop_token)].rstrip()

        logger.info("LLM呼び出し完了 (CoT - ainvoke)")
        logger.info(f"LLM Raw Response:\n{full_response}") # デバッグ用に生の応答を出力

        # --- 応答をパースして表示 ---
        thought_process = "思考プロセスが見つかりません。"
        conclusion = full_response # デフォルトは全応答

        try:
            # 簡単な文字列検索で分割 (より頑健なパースが必要)
            start_tag = "思考プロセス開始:"
            end_tag = "思考プロセス終了"
            conclusion_tag = "結論:"

            start_idx = full_response.find(start_tag)
            end_idx = full_response.find(end_tag)
            conclusion_idx = full_response.find(conclusion_tag)

            if start_idx != -1 and end_idx != -1 and conclusion_idx != -1:
                thought_process = full_response[start_idx + len(start_tag):end_idx].strip()
                conclusion = full_response[conclusion_idx + len(conclusion_tag):].strip()
                logger.debug(f"パース結果: 思考プロセス='{thought_process[:50]}...', 結論='{conclusion[:50]}...'")
            elif conclusion_idx != -1:
                 conclusion = full_response[conclusion_idx + len(conclusion_tag):].strip()
                 thought_process = "(思考プロセス部分が期待した形式で見つかりませんでした)"
                 logger.debug(f"パース結果: 思考プロセスなし, 結論='{conclusion[:50]}...'")
            else:
                logger.warning("応答から思考プロセスと結論のタグが見つかりませんでした。")

        except Exception as parse_err:
            logger.error(f"応答のパースエラー: {parse_err}")
            # パース失敗時は全応答を表示

        # --- Chainlit UIで表示 ---
        async with cl.Step(name="思考プロセス") as step:
            step.output = thought_process

        await cl.Message(content=conclusion).send()

        # ★ 実行完了後、合計トークン数を表示
        total_tokens = token_handler.get_total_tokens()
        await cl.Message(
            content=f"--- トークン使用量 ---\n入力: {total_tokens['input']} トークン\n生成: {total_tokens['generated']} トークン\n合計: {total_tokens['total']} トークン",
            author="System Info",
        ).send()

    except Exception as e:
        logger.error(f"LLM呼び出しエラー: {e}", exc_info=True)
        await cl.ErrorMessage(content=f"申し訳ありません、応答の生成中にエラーが発生しました: {e}").send()

# --- Chainlitの実行 ---
# このファイル (例: app_a_cot.py) をターミナルで以下のように実行します
# chainlit run app_a_cot.py -w
