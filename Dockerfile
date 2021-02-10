FROM python:3.7
RUN mkdir /src
ADD todo_operator.py /src
ADD templates /src/templates
RUN pip install kopf
RUN pip install kubernetes
ENTRYPOINT ["kopf"]
CMD ["run",  "/src/todo_operator.py", "--verbose"]