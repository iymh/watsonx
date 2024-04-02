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

var server = express();
server
   .use(express.urlencoded({extended: false}))
   .use(express.json())
   .use(express.static('public'))

   // CORS
   .use(cors())

   // IBM Cloud
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

   // watsonx.ai
   .post('/generation', async function (req, res) {
      let param = req.body;

      // Check Params
      if (!(param?.model_id)) {
         res.status(500).send({"error": "Invalid params!"});
         return;
      }
      let sendurl = `${process.env.WX_URL}ml/v1/text/generation?version=2023-05-29`;

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

   // Watson Discovery v2
   .post('/api', async (req, res) => {
      let body = req.body;

      // Check Params
      if (!(body.params)) {
         res.status(500).send({"error": "Invalid projectId!"});
         return;
      }

      if (typeof process.env.WD_KEY == 'undefined') {
         console.error('Error: "API_KEY" is not set.');
         console.error('Please consider adding a .env file with API_KEY.');
         process.exit(1);
      }

      switch (body.api) {
         case "query":
            discovery.query(body.params)
               .then(response => {
                  // console.log(JSON.stringify(response.result, null, 2));
                  res.json(response.result);
               })
               .catch(err => {
                  console.log('error:', err);
                  res.status(500).send({"error": "Failed Watson Discovery query."});
               });
            break;

         case "listProjects":
            discovery.listProjects()
               .then(response => {
                  console.log(JSON.stringify(response.result, null, 2));
                  res.json(response.result);
               })
               .catch(err => {
                  console.log('error:', err);
                  res.status(500).send({"error": "Failed Watson Discovery listProjects."});
               });
            break;

         case "listCollections":
            discovery.listCollections(body.params)
               .then(response => {
                  console.log(JSON.stringify(response.result, null, 2));
                  res.json(response.result);
               })
               .catch(err => {
                  console.log('error:', err);
                  res.status(500).send({"error": "Failed Watson Discovery listCollections."});
               });
            break;

         default:
            break;
      }
   });

const port = process.env.PORT || 3000;
server.listen(port, () => {
  // eslint-disable-next-line no-console
  console.log('WD & wx.ai Bridge Server running on port: %d', port);
});