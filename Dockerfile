FROM python:3.11

# set a directory for the app
WORKDIR /usr/src/app

# copy all the files to the container
COPY . .

# from https://stackoverflow.com/questions/55313610/importerror-libgl-so-1-cannot-open-shared-object-file-no-such-file-or-directo
RUN apt-get update && apt-get install libgl1 -y

# install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# tell the port number the container should expose
EXPOSE 5000

# make sure gunicorn is installed
RUN pip install gunicorn

# run the command
#CMD ["python", "./app.py"]
CMD gunicorn -b 0.0.0.0:5000 app:app --timeout 600 --worker-tmp-dir /dev/shm  --threads=8
