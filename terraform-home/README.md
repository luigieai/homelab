# Common errors

## PGAdmin
Because of how pgadmin container works, you neeed to give permission to /alloc/pgadmin folder at nomad node so we can share our data between task allocations:
```shell
mkdir /alloc/pgadmin
sudo chown -R 5050:5050 /alloc/pgadmin
```
Source: https://www.pgadmin.org/docs/pgadmin4/8.1/container_deployment.html#mapped-files-and-directories