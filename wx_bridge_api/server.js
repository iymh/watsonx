import express from 'express';

import dotenv from 'dotenv';
dotenv.config({ debug:true });
import axios from 'axios';

var server = express();
server
   .use(express.urlencoded({extended: false}))
   .use(express.json())

   // CORS
   // .use(cors())
   .use(express.static('public'))

   .get('/token', function (req, res) {
      console.log("***** token *****");

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
         res.status(200).send(response.data);
      })
      .catch(err => {
         console.log('error:', err);
         res.status(500).send({"error": err});
      });
   })

   .post('/generation', async function (req, res) {
      let param = req.body;

      // Check Params
      if (!(param?.model_id)) {
         res.status(500).send({"error": "Invalid params!"});
         return;
      }
      let sendurl = `${process.env.WX_URL}ml/v1-beta/generation/text?version=2023-05-29`;

      let options = {
         headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + param.apikey,
         },
      };
      console.log(param.apikey);
      delete param.apikey;
      param.project_id = process.env.WX_PRJID;
      console.log("***** param *****", param);

      axios.post(
         `${sendurl}`,
         param,
         options
      )
      .then(response => {
         // console.log("response: ", response);
         res.status(200).send(response.data);
      })
      .catch(err => {
         console.log('error:', err);
         res.status(500).send({"error": err});
      });
   })

   .post('/generation_stream', async function (req, res) {
      let param = req.body;

      // Check Params
      if (!(param?.model_id)) {
         res.status(500).send({"error": "Invalid params!"});
         return;
      }      
      let sendurl = `${process.env.WX_URL}ml/v1-beta/generation/text_stream?version=2023-05-29`;

      let options = {
         responseType: 'stream',
         headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + param.apikey,
         },
      };
      console.log(param.apikey);
      delete param.apikey;
      param.project_id = process.env.WX_PRJID;
      console.log("***** param *****", param);

      axios.post(
         `${sendurl}`,
         param,
         options
      )
      .then(response => {
         console.log("response: ", response);
         response.data.on('data',(data)=>{
            if (data) {
               let dt = data.toString('utf8');
               console.log('onData', dt);
               if (dt.includes('event: close')) {
                  res.write("[DONE]");
               } else {
                  res.write(dt);
               }
            }
         });
         response.data.on('end',()=>{
            console.log('Response finished');
            res.end();
         });
         res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      })
      .catch(err => {
         console.log('error:', err);
         res.status(500).send({"error": err});
      });
   })

const port = process.env.PORT || 3000;
server.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log('Watsonx Bridge Server running on port: %d', port);
});