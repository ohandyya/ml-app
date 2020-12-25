# Machine Learning Application

## Cost

See [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/) for the up-to-date cost.

For the frontend, we hav a very lightweight frontend (0.5 GB of RAM and 0.25 vCPU). Assuming we run this task 24 hours for 30 days, the total cost is $8.88 USD.

For the DynamoDB, we have only 2 RCU and 2 WCU. The monthly cost is about $1.17 USD.

For our backend-application, it only runs if there is new jobs to work on. So the cost is negligible.
