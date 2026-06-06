# Automated Catering Service
This document details at a high level the overall function of this automated catering service.
The overall functionality of this system is composed of the script, the database, a locally hosted LLM and a connection to Gemini 2.5 flash.

This script when run, uses the data stored in the database to construct and email a completed
orders pdf to email provided in the main function. The script takes into account the enrolments in a specific session, absences on the given day, students who opted out of catering, dietary tags and extra dietary requirements and manager feedback. The cost is also estimated under the assumption that each session will ask the caterer to make one trip with only one stop being the session itself. Orders are also sent direct to caterers if the run was successful.

![Sequence diagram](diagrams/sequence.png)

## System Architecture
The diagram below describes the intended system architecture. The idea is the system can be run by Carmen when required, drawing on all stored data. There is also a simple draft UI to capture student feedback and orders.

![System architecture](diagrams/architecture.png)

## Database
The diagrams below describe the conceptual and tabular schema for the database. The MOQ data has been left off due to time constraints and AI-generated manager feedback has been used to fill in the feedback table.

![Conceptual schema](diagrams/Conceptual.png)

![Tabular schema](diagrams/tabular.png)


## LLM usage
A locally hosted LLM (Gemma3) has been used. Given the strict and simple requirements given to the LLM, a lightweight model is appropriate for the job. The LLM has been used to ingest and understand manager feedback, understand special dietary requirements and rank dishes from caterers based on feedback.

Gemini 2.5 flash has been used for order pdf validation to ensure it makes sense at a high level and has no obvious gaps.