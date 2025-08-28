FROM ubuntu:latest
WORKDIR /app

# 设置时区（非交互模式）
ENV TZ=Asia/Shanghai
RUN ln -fs /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装依赖（明确指定 netcat 实现，解决包不存在问题）
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    memcached \
    nginx \
    build-essential \
    netcat-openbsd  \
    libstdc++6 \
    wget \
    libnuma-dev \
    && rm -rf /var/lib/apt/lists/*

# 暴露服务端口
EXPOSE 11211 80 8080 3306 22222
# memcached/nginx/masstree 默认端口