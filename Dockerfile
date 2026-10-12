# Dockerfile: StrainScope's app in a container (Phase 8, optional).
#
# A container is a sealed box holding one program together with everything it
# needs: here Linux, Python 3.14, the online copy's exact packages
# (app/requirements.txt) and the project's files. The same box runs on
# Windows, macOS and Linux, with Docker or Podman, and the app inside behaves
# the same wherever the box runs.
#
# Build the image once, then start it (docs/09-packaging.md explains each word):
#
#     docker build -t strainscope .
#     docker run --rm -it -p 8501:8501 strainscope
#
# and open http://localhost:8501. On RHEL 8, `podman` takes the same commands.
# The database is built while the image is made, so the app starts ready.

# The starting box: a small Debian Linux with Python 3.14, the version the
# online copy runs. The full name (docker.io/library/...) saves Podman from
# asking which registry to use.
FROM docker.io/library/python:3.14-slim

# No .pyc files, output shown straight away, no download cache kept in the image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /strainscope

# The packages first, on their own: Docker keeps this step and reuses it on
# the next build as long as app/requirements.txt hasn't changed.
COPY app/requirements.txt app/requirements.txt
RUN python -m pip install -r app/requirements.txt

# Then the project itself (.dockerignore lists what stays out: the toolbox,
# your data, secrets, Git's history).
COPY . .

# Build the database from the committed results (the quick plan, about 15
# seconds), and run everything as an ordinary user rather than as root.
RUN python src/strainscope/pipeline.py database --quiet \
    && useradd --create-home --uid 1000 strainscope \
    && chown -R strainscope:strainscope /strainscope
USER strainscope

# The app listens on port 8501 inside the box; `-p 8501:8501` connects it to
# the same port on your computer. 0.0.0.0 means "answer on every network
# address of the box", which the connection needs.
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app/streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
