sudo apt install -y python3-numpy openjdk-8-jdk libtcmalloc-minimal4 libgoogle-perftools-dev docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER

docker load -i ubuntu_latest.tar
docker build --no-cache -t be_container:v1 -f ./BE.Dockerfile .
docker build --no-cache -t be_container:v1 -f ./LC.Dockerfile .

cd /home/wjy
git clone git@github.com:intel/intel-cmt-cat.git
cd intel-cmt-cat
make
sudo cp ./pqos/pqos /usr/local/bin/
echo "/home/wjy/intel-cmt-cat/lib" | sudo tee /etc/ld.so.conf.d/pqos.conf
sudo ldconfig

cd /home/wjy/SComet/benchmarks/Tailbench/tailbench
bash build.sh harness masstree
