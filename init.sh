sudo apt update
sudo apt install -y autoconf build-essential intel-cmt-cat memcached libmemcached-tools gfortran
ROOT="/home/wjy/SComet"
cd $ROOT

if [ ! -d "benchmarks" ]; then
    mkdir -p "benchmarks"
fi
cd benchmarks

if [ ! -d "memcached" ]; then
    mkdir -p "memcached"
fi
cd memcached
if [ ! -d "mutated" ]; then
    git clone git@github.com:scslab/mutated.git
fi
if [ ! -d "QoS" ]; then
    mkdir -p QoS
fi
if [ ! -d "script" ]; then
    mkdir -p script
fi
cd mutated
git submodule update --init
./autogen.sh && ./configure && make
cd ../script
cat <<EOF > server.sh
/usr/bin/memcached -t \${1:-1} -u root -p 11211 -m 64m -d
EOF
cat <<EOF > client.sh
cd $ROOT/benchmarks/memcached/mutated
rm -rf ../QoS/memcached.log
for((i=0;i<\${1:-1};i++))
do
    echo "create thread \${i}"
    sudo bash -c "client/mutated_memcache 127.0.0.1:11211 \${2:-50000} -n 1 -w 1s -c 1s -s \${3:-600}s  1> ../QoS/memcached_\${i}.log 2>&1" &
    sleep 0.1
done
wait
EOF



