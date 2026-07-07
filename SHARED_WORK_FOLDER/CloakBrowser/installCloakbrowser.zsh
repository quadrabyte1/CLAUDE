pip install cloakbrowser

colima stop
colima start --cpu 4 --memory 8 --disk 60

docker run --rm cloakhq/cloakbrowser cloaktest
