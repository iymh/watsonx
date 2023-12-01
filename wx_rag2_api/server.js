import express from 'express';
import cors from 'cors';

import dotenv from 'dotenv';
dotenv.config({ debug:true });

// for watsonx.ai rest bridge.
import axios from 'axios';

// Watson Discovery
import DiscoveryV2 from 'ibm-watson/discovery/v2.js';

import { IamAuthenticator } from 'ibm-watson/auth/index.js';
const discovery = new DiscoveryV2({
   version: '{version}',
   authenticator: new IamAuthenticator({
      apikey: process.env.WD_KEY,
   }),
   version: '2020-08-30',
   serviceUrl: process.env.WD_BASE_URL,
});

const GENAPI = "v1-beta/generation/text";
// const GENAPI_STREAM = "_stream";
const GENAPI_VER = "version=2023-05-29";

const LLAMA2CHAT_TMPL_SYS_START = `<s>[INST] <<SYS>>\n`;
const LLAMA2CHAT_TMPL_SYS_END = `<</SYS>>\n`;
const LLAMA2CHAT_TMPL_USR_END = `[/INST]\n`;
const PROMPT_Q_MARKER = "質問: ";
const SYSTEM_PROMPT = `${PROMPT_Q_MARKER}に簡潔に答えてください。。日本語のみ出力してください。`;

var server = express();
server
   .use(express.urlencoded({extended: false}))
   .use(express.json())
   .use(express.static('public'))

   // CORS
   .use(cors())

   .post('/answer', async (req, res) => {
      let body = req.body;

      // Check Env
      if ((typeof process.env.WD_KEY == 'undefined') ||
          (typeof process.env.WX_KEY == 'undefined')) {
         console.error('Error: "WD API_KEY" is not set.');
         process.exit(1);
      }
      // Check Params
      if (!body.question) {
         res.status(500).send({"error": "Invalid params!"});
         return;
      }
      
      let resWD = await callDiscovery(body.dc_params, body.question);
      console.log("WD Response: ", resWD);

      let resPrompt = createPromptShot(resWD, body.question);
      console.log("Created Prompt: ", resPrompt);

      let token = await getToken();
      console.log("Cloud Token: ", token);

      let resWX = await callWXai(body.wx_params, resPrompt, token);
      console.log("WX Response: ", resWX);

      let ret_data = ""
      if (resWX.results) {
         ret_data = resWX.results[0];
      }
      res.send(ret_data);
   });

   async function callDiscovery(dc_params, question) {
      return new Promise((resolve, reject)=> {
         console.log("[callDiscovery]", question, dc_params);

         let send_params = dc_params;
         if (!(send_params?.projectId)) {
            send_params = {
               "projectId": "",
               // "collectionIds":[],
               // "filter": "",
               "passages":{
                  "enabled":true,
                  "find_answers":true,
                  "per_document":true
               },
               "count":3,
               // "aggregation":"",
               // "_return":[],
               "naturalLanguageQuery":""
            };
         }

         // add WD Project ID from env file.
         if (!send_params.projectId) {
            send_params.projectId = process.env.WD_PRJID;
         }
         send_params.naturalLanguageQuery = question;

         discovery.query(send_params)
            .then(response => {
               resolve(response.result);
            })
            .catch(err => {
               console.log('error:', err);
               reject(err);
            });
      });
   };

   function createPromptShot(wd_json, question) {
      console.log("[createPromptShot] ", wd_json, question);
      if (wd_json.results.length <= 1) return null;

      let prompt = "";
      wd_json.results.forEach(item => {
      let ans_cof = item.document_passages?.[0]?.answers?.[0]?.confidence;
      // Use AnswerFindings Confidence 0.5point over.
      if (ans_cof >= 0.5) {
         let ans = item.document_passages?.[0]?.answers?.[0]?.answer_text;
         let psg = item.document_passages?.[0]?.passage_text;

         // Remove <em> tags.
         psg = psg.replace(/<em>/g,'').replace(/<\/em>/g,'');

         if (prompt.length > 0) prompt += "\n\n";
         prompt += `${ans}\n\n${psg}`;
      } else {
         if (item.name && item.description) {
            prompt += `タイトル: ${item.name}\n詳細: ${item.description}\n`;
         }
      }
      });
      prompt += `\n\n${PROMPT_Q_MARKER}${question}`;

      return prompt;
   };

   async function getToken() {
      return new Promise((resolve, reject)=> {
         console.log("[getToken]");
         axios.post(
            `${process.env.AUTH_URL}`,
            {
               "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
               "apikey":`${process.env.WX_KEY}`
            },
            {
               headers: {
                  "Content-Type": "application/x-www-form-urlencoded",
               },
            }
         )
         .then(response => {
            console.log("response: ", response.status);
            resolve(response.data.access_token);
         })
         .catch(err => {
            console.log('error:', err);
            reject({"error": err});
         });
      });
   };

   async function callWXai(wx_params, fewshot, token) {
      return new Promise((resolve, reject)=> {
         console.log("[callWXai]", wx_params);
         // Check Params
         if (!fewshot) {
            res.status(500).send({"error": "Nothing WD Results."});
            return;
         }

         let send_params = wx_params;

         // set default llm parameters.
         if (!(send_params.model_id)) {
            send_params.model_id = "meta-llama/llama-2-70b-chat";
         }
         if (!(send_params.parameters)) {
            send_params.parameters = {};
         }
         if (!(send_params.parameters?.decoding_method)) {
            send_params.parameters.decoding_method = "greedy";
         }
         if (!(send_params.parameters?.min_new_tokens)) {
            send_params.parameters.min_new_tokens = 0;
         }
         if (!(send_params.parameters?.max_new_tokens)) {
            send_params.parameters.max_new_tokens = 100;
         }

         let prompt = "";
         if ((/llama-2-.*-chat/).test(send_params.model_id)) {
            // set optimized prompt for llama2 chat
            prompt = `${LLAMA2CHAT_TMPL_SYS_START}`;
            prompt += `${SYSTEM_PROMPT}${LLAMA2CHAT_TMPL_SYS_END}\n`;
            prompt += `${fewshot}\n${LLAMA2CHAT_TMPL_USR_END}`;
         } else {
            prompt = `${SYSTEM_PROMPT}\n\n${fewshot}\n\n`;
         }
         console.log("Prompt: ", prompt);
         send_params.input = prompt;

         send_params.project_id = process.env.WX_PRJID;

         let sendurl = `${process.env.WX_URL}${GENAPI}?${GENAPI_VER}`;
         let options = {
            headers: {
               "Content-Type": "application/json",
               Authorization: "Bearer " + token,
            },
         };
         axios.post(
            `${sendurl}`,
            send_params,
            options
         )
         .then(response => {
            console.log("response: ", response.status);
            resolve(response.data);
         })
         .catch(err => {
            console.log('error:', err);
            reject(err);
         });
      });
   };

const port = process.env.PORT || 3000;
server.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log('RAG2.0 Bridge Server running on port: %d', port);
});