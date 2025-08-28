FROM ubuntu:latest
WORKDIR /app

# 设置时区（非交互模式）
ENV TZ=Asia/Shanghai
RUN ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装依赖并修复 numpy 安装问题
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    memcached \
    nginx \
    build-essential \
    netcat-openbsd \
    libstdc++6 \
    python3 \
    python3-pip \
    wget \
    libnuma-dev \
    libgoogle-perftools-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --break-system-packages numpy pandas matplotlib scipy # 关键修改

# 暴露服务端口
EXPOSE 11211 80 8080 3306 22222
