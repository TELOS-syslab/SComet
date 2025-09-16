sudo apt install -y python3-numpy openjdk-8-jdk libtcmalloc-minimal4 libgoogle-perftools-dev docker.io sshpass
sudo systemctl enable --now docker
sudo usermod -aG docker $USER


image_exists() {
    docker image inspect "$1" > /dev/null 2>&1
    return $?
}

if ! image_exists "ubuntu:latest"; then
    if [ -f ubuntu_latest.tar ]; then
        echo "Loading ubuntu_latest.tar..."
        docker load -i ubuntu_latest.tar
    else
        echo "Error: ubuntu_latest.tar not found!"
        exit 1
    fi
else
    echo "ubuntu:latest already exists, skipping load."
fi

if ! image_exists "be_container:v1"; then
    echo "Building BE container..."
    docker build --no-cache -t be_container:v1 -f ./BE.Dockerfile .
else
    echo "be_container:v1 already exists, skipping build."
fi

if ! image_exists "lc_container:v1"; then
    echo "Building LC container..."
    docker build --no-cache -t lc_container:v1 -f ./LC.Dockerfile .
else
    echo "lc_container:v1 already exists, skipping build."
fi

echo "installing pqos..."
cd /home/wjy
if [ ! -d intel-cmt-cat ]; then
    git clone https://github.com/intel/intel-cmt-cat.git
fi
cd intel-cmt-cat
make
sudo cp ./pqos/pqos /usr/local/bin/
echo "/home/wjy/intel-cmt-cat/lib" | sudo tee /etc/ld.so.conf.d/pqos.conf
sudo ldconfig

echo "installing tailbench..."
cd /home/wjy/SComet/benchmarks
if [ ! -d Tailbench ]; then
    git clone git@github.com:TELOS-syslab/SComet-realmachine-tailbench.git
    mv SComet-realmachine-tailbench Tailbench
else
    cd Tailbench
    git pull
    cd ..
fi
cd /home/wjy/SComet/benchmarks/Tailbench/tailbench
bash build.sh harness masstree
sudo chmod -R +x /home/wjy/SComet/benchmarks/
