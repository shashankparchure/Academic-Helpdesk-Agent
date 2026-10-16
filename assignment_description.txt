In
this assignment you need to design a multiagent Academic Helpdesk
Agent. The agent can answer questions about the academic programs,
course contents, academic rules and regulations and
draft an email to course instructor to apply for sick-leave or seek
permission for makeup exams. It should be able to handle questions
such as, “What is the attendance requirement to sit in the Major
exam?”. “What is the slot for the course Autonomous Systems?”,
“How many 400 level electives have been floated by the Humanities
department in this semester?”, “How many Open Elective credits do
I need to earn in order to get a B.Tech. Degree?”, "Write an email to the course instructor of CSL7570 that I need leave for 2 days".


For
any other question, such as, “What are the available dining options
on the campus?”, or "What is the best way to reach the campus from Jodhpur city center?", the agent should answer that it does not know,
instead of guessing an answer.





As
part of this project, the team should collect 20 to 30 real documents
related to rules and regulations, time table, course registration,
recent office orders, faculty email Ids, etc. Personal data can be
replaced with dummy values.





The
agent should be using RAG and would be requiring several tools to
assist the process of generating a response. Example tools can be:
searching the most relevant chunks from the vector store, looking up
time table and course codes from CSV files, looking up email ID of
the instructor of a course, writing
an email draft for the student to review (the email need not be actually sent). The agent should also keep
a log of the questions it cannot answer, so that these questions can
be referred to the human to answer. The generated answer should refer
to/cite the document it came from.





The
project should be executable on a laptop/computer with 16GB RAM. You
can use Google-ADK for the agent framework. The
ADK can invoke the Ollama-hosted models through its LiteLLM
connector. You can use 8B chat models such as Qwen3 or Llama 3.1. For
implementing RAG you can use a local embedding model via Ollama and a
local vector store such as ChromaDB.



Once
the base version with a single agent, RAG pipeline and all
the tools are incorporated in the implementation, you can augment it
to a multi-agent version. There can be a helpdesk orchestrator which
can transfer the question to a policy agent (to answer questions
related to rules and regulations and curriculum), schedule agent (to
answer questions related to slots and time table) and an email agent
(to get the instructor contact and draft an email).





For
a collection of 20 to 30 prompts, analyze the performance of the
multi agent system on metrics such as accuracy of answers,
groundedness (correct citation) of answers, correct refusals to
answer out of scope questions. You can also replace the LLM used and
see the performance. Note down the questions whose answers have changed
when using multiple runs.



Submit
the code repository with a README file, the set of questions, and a
report with the findings.