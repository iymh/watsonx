# app_agent.py
import chainlit as cl
import asyncio
from dotenv import load_dotenv
import os
import logging

from langchain.agents import AgentExecutor, create_react_agent, Tool
from langchain_core.prompts import ChatPromptTemplate
# from langchain import hub # ReActプロンプト取得用 (カスタムプロンプトを使用するため不要)
from langchain_community.tools import DuckDuckGoSearchRun

# 提供された req_wxai モジュールをインポート
# (この app.py と同じディレクトリにあるか、Pythonパスが通っている必要があります)
try:
    # wx_agent ディレクトリには req_wxai.py がある想定
    import req_wxai as GEN
except ImportError:
    print("エラー: req_wxai.py が見つかりません。app_agent.py と同じディレクトリに配置してください。")
    exit()

# LOG設定
# ログレベルを INFO に変更 (DEBUG は詳細すぎる場合)
logging.basicConfig(format='[%(asctime)s] %(levelname)s: %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# .env ファイルから環境変数を読み込む
load_dotenv()

# --- Chainlit アプリケーション ---
@cl.on_chat_start
async def start_chat():
    """
    チャットセッション開始時に呼び出され、LLM、ツール、Agent Executorを初期化します。
    """
    logger.info("チャットセッション開始 (Agentモード)")
    try:
        # --- LLMの準備 ---
        # Agent用に最大トークン数を調整 (必要に応じて変更)
        llm_params = GEN.Params(max_new_tokens=4096)
        llm = GEN.setLlm(llm_params)
        logger.info(f"使用モデル: {llm.model_id}")

        # --- ツールの準備 ---
        search = DuckDuckGoSearchRun()
        tools = [
            Tool(
                name="DuckDuckGo Search",
                func=search.run,
                description="現在の出来事や最新情報、特定のトピックについてWebで検索する必要がある場合に使用します。一般的な知識に関する質問には使用しないでください。"
            )
        ]
        logger.info(f"利用可能なツール: {[tool.name for tool in tools]}")

        # --- Agentの準備 ---
        # ReActプロンプトテンプレート (モデルやタスクに合わせて調整可能)
        # 参考: https://smith.langchain.com/hub/hwchase17/react
        prompt_template = """
以下の質問にできる限り答えてください。次のツールを利用できます:
{tools}

次の形式を使用してください:

Question: 回答する必要のある入力質問
Thought: 何をすべきか常に考える必要があります
Action: 実行するアクション。[{tool_names}] のいずれかである必要があります
Action Input: アクションへの入力
Observation: アクションの結果
... (この思考/アクション/アクション入力/観察はN回繰り返すことができます)
Thought: これで最終的な答えがわかりました
Final Answer: 元の入力質問に対する最終的な答え（日本語で記述）

始めましょう！

Question: {input}
Thought:{agent_scratchpad}
"""
        prompt = ChatPromptTemplate.from_template(prompt_template)
        logger.debug("ReActプロンプトテンプレートを設定")

        # Agentを作成
        agent = create_react_agent(llm, tools, prompt)
        logger.debug("ReAct Agentを作成")

        # Agent Executorを作成
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True, # Agentの思考プロセスをログに出力 (デバッグ用)
            # handle_parsing_errors=True # パースエラー時にAgentにエラーを伝えて継続させる場合
        )
        logger.debug("Agent Executorを作成")

        # Agent Executorをユーザーセッションに保存
        cl.user_session.set("agent_executor", agent_executor)

        await cl.Message(
            content=f"こんにちは！ **{llm.model_id}** を使ったReAct Agentで応答します。Web検索も可能です。"
        ).send()
        logger.info("Agent Executorの初期化完了")

    except Exception as e:
        logger.error(f"初期化エラー: {e}", exc_info=True)
        await cl.ErrorMessage(content=f"Agentの初期化中にエラーが発生しました: {e}").send()

@cl.on_message
async def main(message: cl.Message):
    """
    ユーザーからのメッセージ受信時に呼び出され、Agent Executorを実行します。
    """
    agent_executor = cl.user_session.get("agent_executor")

    if not agent_executor:
        await cl.ErrorMessage(content="エラー: Agentが初期化されていません。ページをリロードしてください。").send()
        return

    user_query = message.content
    logger.info(f"受信メッセージ: {user_query}")

    # Chainlitのコールバックハンドラを設定 (ストリーミング表示用)
    cb = cl.LangchainCallbackHandler(
        stream_final_answer=True # 最終回答をストリーム表示
    )

    try:
        logger.info("Agent実行開始")
        # Agentを実行し、思考プロセスと最終回答をストリーミング表示
        # astream_log は思考ステップを含む詳細なログを非同期で返す
        response_generator = agent_executor.astream_log(
            {"input": user_query},
            config={"callbacks": [cb]} # コールバックハンドラを渡してUI表示を任せる
        )

        # response_generator を非同期でイテレートして処理を完了させる
        # コールバックハンドラがUIへのストリーミングを行うため、ここでは特別な処理は不要
        async for chunk in response_generator:
            # 必要であればチャンクの内容をログに出力してデバッグ
            # logger.debug(f"Agent Log Chunk: {chunk}")
            pass

        # stream_final_answer=True の場合、最終回答の表示はコールバックハンドラが行う
        logger.info("Agent実行完了")

    except Exception as e:
        logger.error(f"Agent実行エラー: {e}", exc_info=True)
        # エラーメッセージをUIに表示
        await cl.ErrorMessage(content=f"Agentの実行中にエラーが発生しました: {e}").send()

# --- Chainlitの実行 ---
# このファイル (app_agent.py) をターミナルで以下のように実行します
# chainlit run app_agent.py -w
