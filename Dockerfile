FROM alpine:3.20

# Install base tools and Python
RUN apk add --no-cache \
    bash \
    curl \
    ca-certificates \
    htop \
    python3 \
    py3-pip \
    py3-setuptools \
    py3-wheel \
    build-base \
    libffi-dev \
    musl-dev \
    gfortran \
    openblas-dev \
    shadow \
    tzdata

# Install uv using official script, and move binary to /usr/local/bin
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/

# Confirm uv is available
RUN uv --version

# Copy the simple shell init script
COPY simple-init /init
RUN chmod +x /init

# Add user for auto-login
RUN useradd -m -s /bin/bash scientist

# Create proper terminal devices and setup (if they don't exist)
RUN (mknod -m 666 /dev/tty c 5 0 || true) && \
    (mknod -m 666 /dev/console c 5 1 || true) && \
    (mknod -m 666 /dev/null c 1 3 || true)

# Setup terminal environment
RUN echo '#!/bin/bash' > /usr/local/bin/start-shell && \
    echo 'export TERM=xterm' >> /usr/local/bin/start-shell && \
    echo 'export PS1="lab-vm:\w # "' >> /usr/local/bin/start-shell && \
    echo 'cd /home/scientist' >> /usr/local/bin/start-shell && \
    echo 'su - scientist' >> /usr/local/bin/start-shell && \
    chmod +x /usr/local/bin/start-shell

USER scientist
WORKDIR /home/scientist

# Install scientific packages with uv (no cache)
ENV UV_CACHE_DIR="/tmp/uv-cache"
RUN uv venv .venv && \
    . .venv/bin/activate && \
    uv pip install --no-cache-dir numpy pandas scipy matplotlib seaborn ipython hypha-rpc && \
    rm -rf $UV_CACHE_DIR ~/.cache/pip

# Ensure venv is active on login
ENV PATH="/home/scientist/.venv/bin:$PATH"

# Terminal environment variables
ENV TERM=xterm
ENV PS1="lab-vm:\w # "

# Add terminal setup to user's bashrc
USER root
RUN echo 'export TERM=xterm' >> /home/scientist/.bashrc && \
    echo 'export PS1="lab-vm:\w # "' >> /home/scientist/.bashrc && \
    echo 'source /home/scientist/.venv/bin/activate' >> /home/scientist/.bashrc && \
    chown scientist:scientist /home/scientist/.bashrc

USER scientist

# CMD ["/bin/bash"]
