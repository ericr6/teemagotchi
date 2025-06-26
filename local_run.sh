#!/bin/bash



mkdir -p ./tmp/iexec_in
mkdir -p ./tmp/iexec_out
rm -rf tmp/iexec_out/*
cp input_example/sample_5.txt tmp/iexec_in/data.txt
echo "How is the team motivation today?" > ./tmp/iexec_in/question.txt

docker run -v ./tmp/iexec_in:/iexec_in -v ./tmp/iexec_out:/iexec_out -e IEXEC_IN=/iexec_in -e IEXEC_OUT=/iexec_out ericro/teamagotchi-local:0.0.1 

echo "check result ..." 
cat tmp/iexec_out/result.txt