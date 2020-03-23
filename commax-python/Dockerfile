FROM python:3.7-alpine

ENV LANG C.UTF-8
ENV TZ=Asia/Seoul

# Copy data for add-on
COPY run.sh /
COPY pycommax /pycommax

# Install requirements for add-on
RUN pip install paho-mqtt

WORKDIR /share

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
