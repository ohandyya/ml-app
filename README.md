# Machine Learning Application

## Goal

- An `architecture` for hosting `machine learning prototype` that are `scalable`, `easily maintaiable`, and `cost effective` for `research scientists`.

  - The type of machine learnig algoirhtm is not the focus. It is the `architecture` that we are interested in.

  - We are interested in hosting `machine learning prototype`. It is a `prototype`, which means the goal is to demonstrate the machine learning model, and fancy UI is not the focus. For `machine learning`, there are generically two types of predictions. The first type is realtime prediction, that is, prediction that can happen within minutes. The second type is non-realtime (or batch) prediction, that is, prediction that may take minutes to hours to complete. And due to the complexity of machine learing applications, it requires a heavy computing engine, e.g., 10+ GB of memory and/or high-end CPU and/or high-end GPU.

  - The application should be `scalable`. That is, the application should work even if there are 100+ users that is using the application.

  - The application should be `easily maintaiable`. We are a reserach scientists, and not dev ops. We are not interested in spending a lot of time and effort to maintain the application. We want to reduce the maintenance as much as possible.

  - The application shoudl be `cost effective`. In other words, we want to seperate long-running tasks (such as UI frontend) and short-lived compute engine (such as the prediction services). To control the cost, we should NOT createa BIG machine that hosts everything, as it will be expensive.

  - We are `research scientists`. We have greate math skill and can create algorithms to solve business problems. However, we need to way to quickly show the world our achievement.


## Architecture Overview

[Google drawing source](https://docs.google.com/drawings/d/1XFEogSXvjYJVDbUxh9cotJs3w1R5XU13H00o495ZPfk/edit?usp=sharing)

<p align="center"><img src="ml-app-architecture.jpg" height="700px" /></p>


## Techincal Details

- Add Application Load Balancer (ALB) to ECS Service

    - https://appfleet.com/blog/route-traffic-to-aws-ecs-using-application-load-balancer/

## Operation Cost

See [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/) for the up-to-date cost.

For the frontend, we hav a very lightweight frontend (0.5 GB of RAM and 0.25 vCPU). Assuming we run this task 24 hours for 30 days, the total cost is $8.88 USD.

For the DynamoDB, we have only 2 RCU and 2 WCU. The monthly cost is about $1.17 USD.

For our backend-application, it only runs if there is new jobs to work on. So the cost is negligible.
