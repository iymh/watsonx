# app_a_simple.py (ファイル名を変更して保存することを推奨)
import chainlit as cl
import asyncio
from dotenv import load_dotenv
import os
import logging

# LangChain Core (PromptTemplate)
from langchain_core.prompts import PromptTemplate

# 提供された req_wxai モジュールをインポート
try:
    import req_wxai as GEN
except ImportError:
    print("エラー: req_wxai.py が見つかりません。app_a_simple.py と同じディレクトリに配置してください。")
    exit()

# LOG設定
logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)

# .env ファイルから環境変数を読み込む
load_dotenv()

# --- Chainlit アプリケーション ---
@cl.on_chat_start
async def start_chat():
    """
    チャットセッション開始時に呼び出される関数 (Simple usecase 用)。
    LLMチェーンを初期化し、ユーザーセッションに保存します。
    """
    logger.info("チャットセッション開始 (Simple usecase)")
    try:
        # デフォルトのパラメータでLLMチェーンを設定
        # req_wxai.py のデフォルト値を使用
        params = GEN.Params(
            # 必要に応じてデフォルト値をここで上書きできます
            # modelname="...",
            max_new_tokens=8192, # ストリーミング用に調整
        )
        logger.info(f"使用モデル: {params.modelname}, パラメータ: {params.dict(exclude={'prompt'})}")

        # req_wxai.py の setLlmChain を使用してLangChainオブジェクトを取得
        # 注意: setLlmChain 内のプロンプトテンプレートが Simple usecase に適しているか確認
        # (CoT用テンプレートになっている場合は req_wxai.py を修正するか、ここで上書き)
        # --- プロンプトテンプレートをここで定義する場合 ---
        # llm = GEN.setLlm(params) # LLMインスタンスを取得
        # simple_template_string = "日本語で答えてください : {question}"
        # ptemplate = PromptTemplate(
        #     input_variables=["question"],
        #     template=simple_template_string,
        # )
        # lchain = ptemplate | llm
        # ---------------------------------------------
        # req_wxai.py の setLlmChain をそのまま使う場合
        lchain = GEN.setLlmChain(params)


        # LLMチェーンとパラメータをユーザーセッションに保存
        cl.user_session.set("llm_chain", lchain)
        cl.user_session.set("llm_params", params)

        await cl.Message(
            content=f"こんにちは！ **{params.modelname}** を使って応答します。質問を入力してください。"
        ).send()
        logger.info("LLMチェーンの初期化完了")

    except Exception as e:
        logger.error(f"初期化エラー: {e}", exc_info=True)
        await cl.ErrorMessage(
            content=f"チャットの初期化中にエラーが発生しました: {e}\n環境変数（API_KEY, WML_URL, WX_PRJID）が正しく設定されているか確認してください。"
        ).send()


############ Simple　usecase
@cl.on_message
async def main(message: cl.Message):
    """
    ユーザーからのメッセージ受信時に呼び出される関数 (Simple usecase)。
    保存されたLLMチェーンを使って応答を生成し、ストリーミング表示します。
    """
    lchain = cl.user_session.get("llm_chain")
    params = cl.user_session.get("llm_params")

    if not lchain or not params:
        await cl.ErrorMessage(content="エラー: LLMチェーンが初期化されていません。ページをリロードしてください。").send()
        return

    user_query = message.content
    logger.info(f"受信メッセージ: {user_query}")

    # ストリーミング応答用の空メッセージを作成
    msg = cl.Message(content="")
    await msg.send()

    final_response = ""
    try:
        # req_wxai.py の setLlmChain が返すオブジェクト (LCEL Runnable) は astream を持つはず
        if hasattr(lchain, 'astream'):
            logger.info("LLM呼び出し開始 (ストリーミング - astream)")
            # LangChain オブジェクトの astream メソッドを使用
            async for chunk in lchain.astream({"question": user_query}):
                await msg.stream_token(chunk)
                final_response += chunk
            await msg.update()
            logger.info("LLM呼び出し完了 (ストリーミング - astream)")
        # 古い形式のストリーム関数 (req_wxai.py に call_genai_stream があれば)
        elif hasattr(GEN, 'call_genai_stream'):
             logger.info("LLM呼び出し開始 (ストリーミング - call_genai_stream)")
             # params.prompt = user_query # パラメータにプロンプトを設定する必要がある
             async for chunk in GEN.call_genai_stream(params): # params を渡す必要があるか確認
                 await msg.stream_token(chunk)
                 final_response += chunk
             await msg.update()
             logger.info("LLM呼び出し完了 (ストリーミング - call_genai_stream)")
        # ストリーミング非対応の場合 (ainvoke)
        else:
            logger.info("LLM呼び出し開始 (非ストリーミング)")
            # 通常の invoke を使用
            response = await lchain.ainvoke({"question": user_query}) # 非同期呼び出し
            await msg.update(content=response) # 全文を一度に更新
            final_response = response
            logger.info("LLM呼び出し完了 (非ストリーミング)")


    except Exception as e:
        logger.error(f"LLM呼び出しエラー: {e}", exc_info=True)
        await msg.update(content=f"申し訳ありません、応答の生成中にエラーが発生しました: {e}")


# --- Chainlitの実行 ---
# このファイル (例: app_a_simple.py) をターミナルで以下のように実行します
# chainlit run app_a_simple.py -w
