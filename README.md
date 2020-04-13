# stopcovid-lambdas

## Architecture

See [architecture overview](docs/README.md).

## The simulator

You can simulate the core of dialog processing on the command line — by feeding the dialog engine with command-line entries rather than entries from a kinesis stream. Try it out by running `python simulator.py`.

## Deployment
We deploy from the command line using the serverless framework. Once you are a member of the serverless project you can deploy to  

- dev: `serverless deploy -s dev --env development`
- prod: `serverless deploy -s prod --env production`

## CI
We use [black](https://black.readthedocs.io/en/stable/) for code formatting and flake8 for linting, with a custom rule setting maximum line length to 100.
- `black --config black.toml .`
- `flake8`



## Local development
There are a series of [sample events](sample_events/) in the project. You can run them against dev:
- `serverless invoke local -f sendMessage -p sample_events/send_message.json`

Run `docker-compose up` in the `db_local` directory