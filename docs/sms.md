# SMS Context

The SMS Context is responsible for sending and receiving messages with users. It includes our integration with Twilio.

## Inbound SMS

Inbound messages are messages from users to the stopCOVID system. All inbound messages arrive in the system via the Twilio webhook. For each message, we enqueue a command in the Dialog Context's command queue to process the message.

## Outbound SMS

Outbound messages are messages from the stopCOVID system to users. Currently all outbound messages are triggered by events from the Dialog Context.

![outbound SMS](sms_context_inbound.png)

## Message logging
sdgsg

## Components

* The twilio webhook: A lambda reachable via Amazon's API Gateway