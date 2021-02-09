FROM python:3.7
RUN mkdir /src
ADD hello_world.py /src
ADD templates /src/templates
RUN pip install kopf
RUN pip install kubernetes
ENTRYPOINT ["kopf"]
CMD ["run",  "/src/hello_world.py", "--verbose"]