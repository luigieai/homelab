
terraform {
  required_providers {
    nomad = {
      source  = "hashicorp/nomad"
      version = "2.4.0"
    }
  }
  backend "pg" {
    conn_str = "postgres://postgres@100.64.0.7:5432/terraform_backend"
    #conn_str = "postgres://postgres@192.168.5.4:5432/terraform_backend"
  }
  required_version = ">= 0.14"
}

/*

VOCE PRECISA FAZER UM TUNEL PRA ACESSAR O SQL DO LAB. E TESTAR O INIT DO TERRAFORM. BOLAR UM JEITO DE SEMPRE RODAR SAPORRA DE TF DO LAB

PASSWORD: 
read -s PGPASSWORD
export PGPASSWORD
*/


# Configure the Nomad provider.
provider "nomad" {
  address = "http://100.64.0.5:4646" 
}
