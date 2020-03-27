# stopcovid-lambdas
stopcovid.co


# How to invoke lambdas locally
`serverless invoke local -f routeInboundSMS -p sms_event.json`


# Deploy to dev
`serverless deploy -s dev --env development`

# Deploy to prod
`serverless deploy -s prod --env production`


[Architecture overview](https://docs.google.com/drawings/d/18OmG9dzR2g8XuAYoUAFHrQ53Gxsg1CCak_YEe_6TUy8/edit)
