# Description

This FastAPI app converts pdf and xml files into a single pdf file with the FacturX format.

# Launch API

## Docker

### Build
`docker build -t my-factur-x-api:dev .`
### Run
`docker run --name my-container -p 8080:80 my-factur-x-api:dev`
## Docker Compose

### Up

`docker-compose --profile elastic up -d`
`docker-compose --profile api up`

### Down

`docker-compose down`

