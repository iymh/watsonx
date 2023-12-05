# watsonx RAG2.0 Server Build Assets

<div>
  <img src="./doc/chart-rag2.png" width="80%">
</div>

## 前提条件
* [wd_bridge_api](https://github.com/iymh/wd_bridge_api), [wx_bridge_api](../wx_bridge_api/) の環境構築ができている。
* APIKeyが作成できていてapi経由でアクセスできている状態。

## 開発ツールのインストール
* [Node.jsとnvmのインストール](https://kazuhira-r.hatenablog.com/entry/2021/03/22/223042)
  * "node -v", "npm -v" コマンドを確認

## ローカル環境でプロジェクトの確認
### ソースのダウンロード
* Gitからソース一式をクローン、or zipファイルダウンロード
```
 "watsonx.zip" ファイルを展開
```

### プロジェクトのファイルをインストール
* 展開したソースのディレクトリに "cd"してからインストールを実行
```
"cd ./wx_rag2_api"
npm install
```
* "package.json"ファイルのあるフォルダ内で上記を実行
* "package.json" 記載のモジュールが "node_modules"配下に展開される

## 開発手順
### watsonxとIBMCloudのサービス情報をセットする
  * 展開したフォルダ内で ".env_sample"ファイルを ".env"ファイルにコピーする
  * 作成した"プロジェクトID"と"APIキー"を貼り付ける
    * WD_BASE_URL, WD_KEY,
    * WX_KEY, WX_PRJID

### watsonx .ai & WatsonDiscovery サービスとの中継サーバを起動しコンテンツの動作を確認
```
node server.js
```
* 起動成功で "http://localhost:3000/index.html" でローカルサーバのコンテンツが表示される
* 質問文を入力して、検索を実行
* 要約された一文の回答が表示されることを確認する
* 各パラメータをテキストで指定する
  * 上記の envファイルのWX_PRJID はデフォルト値。入力テキストが優先される。
  <div>
    <img src="./doc/contents1.png" width="80%">
  </div>

## コンテナを外部サーバとしてデプロイ
* [CodeEngineへ作成](https://github.com/iymh/wd_bridge_api/blob/main/doc/ce/deploy_codeengine.md) こちらを参考にコンテナアプリを作成する

### アプリ作成(上記との変更点)
  * github のパスを以下の用に指定する
    <div>
      <img src="./doc/ce_create.png" width="50%">
    </div>
### 環境変数をセットする
  * ローカル環境のenvファイルの中身を貼り付ける
    <div>
      <img src="./doc/ce_env.png" width="90%">
    </div>
### アプリを確認する
  * 「アプリケーションのテスト」を起動して動作を確認する
  * URLをコピーする
    <div>
      <img src="./doc/ce_dashboard.png" width="90%">
    </div>
### RESTサーバーを確認する
  ~~~
  https://wx-rag2.xxxxxxxxxx.jp-tok.codeengine.appdomain.cloud/answer
  ~~~
  * POSTMANでリクエストを送る
    <div>
      <img src="./doc/postman1.png" width="80%">
    </div>
  * cURLの場合
    ~~~
    curl --location 'https://wx-rag2.xxxxxxxxxx.jp-tok.codeengine.appdomain.cloud/answer' \
    --header 'Content-Type: application/json' \
    --data '{
        "question":"一元配置分散分析とは？",
        "dc_params":{
          "projectId":"xxxxxxxxxxxx",
          "count":3
        },
        "wx_params":{
            "model_id": "meta-llama/llama-2-70b-chat"
            ,"max_new_tokesn":50
        }
    }'
    ~~~

## Watsonx Assistant の設定

### Assistantを作成
  * 新規作成
    <div>
      <img src="./doc/wa_new1.png" width="48%">
      <img src="./doc/wa_new2.png" width="50%">
    </div>

### Custom Extensionに登録
  * 登録
    <div>
      <img src="./doc/wa_inte1.png" width="48%">
      <img src="./doc/wa_inte2.png" width="50%">
    </div>
  * Custom Extension 作成
    <div>
      <img src="./doc/wa_ext1.png" width="48%">
      <img src="./doc/wa_ext2.png" width="50%">
    </div>
  * OpenAPIの設定ファイルを登録
    * "/forWA/openapi.json" を編集する
    * CodeEngine等に作成した外部URLを貼り付ける
      <div>
        <img src="./doc/vs1.png" width="80%">
      </div>
    * "/forWA/openapi.json" を登録する
      <div>
        <img src="./doc/wa_ext3.png" width="80%">
      </div>
      
    * API仕様にエラーが出ていないか確認する
      <div>
        <img src="./doc/wa_ext4.png" width="80%">
      </div>

  * 作成したExtensionをを登録設定
    <div>
      <img src="./doc/wa_ext5.png" width="48%">
      <img src="./doc/wa_ext6.png" width="50%">
    </div>
    * これでActionsの中で使用できるようになります。

### Actionsの作成
  * アクションの新規作成
    <div>
      <img src="./doc/wa_action_create1.png" width="48%">
      <img src="./doc/wa_action_create2.png" width="50%">
    </div>

  * ステップ1の作成
    * "Assistant says" に質問文を入力します。
    * "Define customer response" に "Free text" を選択します。
    <div>
      <img src="./doc/wa_step1_1.png" width="48%">
      <img src="./doc/wa_step1_2.png" width="50%">
    </div>

  * ステップ2の作成
    * "Is taken" を "with conditions" に変更します。
    * "Conditions" に "Step1" の選択肢がデフォルトでセットされます。
      <div>
        <img src="./doc/wa_step2_1.png" width="80%">
      </div>
    * "Assistant says" にアプリ接続する旨のの文言を入力します。
    * "And then" に "Use an extension" を選択します。
      <div>
        <img src="./doc/wa_step2_2.png" width="80%">
      </div>
    * "Parameters" に "値をセットします。
    * "question" に "Step1" の値をセットします。
      <div>
        <img src="./doc/wa_step2_3.png" width="49%">
        <img src="./doc/wa_step2_4.png" width="49%">
      </div>
    * "wx_params.model_id" に "meta-llama/llama-2-70b-chat" を入力します。
      <div>
        <img src="./doc/wa_step2_5.png" width="80%">
      </div>

  * ステップ3の作成
    * "Is taken" を "with conditions" に変更します。
    * "Conditions" に "Step2" のレスポンス状態をセットします。
    * "Ran successfully"を選択します。
      <div>
        <img src="./doc/wa_step3_1.png" width="49%">
        <img src="./doc/wa_step3_2.png" width="49%">
      </div>
    * "Assistant says" に "Step2" の結果をセットします。
    * サーバからのJSONレスポンスの"body.generated_text"をセットします
      <div>
        <img src="./doc/wa_step3_3.png" width="49%">
        <img src="./doc/wa_step3_4.png" width="49%">
      </div>
    * "And then" に "End the action" 等を指定します。
      <div>
        <img src="./doc/wa_step3_5.png" width="80%">
      </div>

### Actionsの初期表示を指定
  * "Set by assistant" の "Greet customer"を選択します。
    <div>
      <img src="./doc/wa_init1.png" width="80%">
    </div>
  * 初期表示の挨拶文を入力します。
  * "Go to a subaction" に 作成したアクションを選択します。
    <div>
      <img src="./doc/wa_init2.png" width="49%">
      <img src="./doc/wa_init3.png" width="49%">
    </div>

### プレビュー
  * 初期表示に作成したアクションが実行されていることを確認します。
    <div>
      <img src="./doc/wa_preview1.png" width="80%">
    </div>
  * 質問文を入力し、回答が得られることを確認します。
    <div>
      <img src="./doc/wa_preview2.png" width="80%">
    </div>
