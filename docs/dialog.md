# Dialog Context

The dialog context is the core of the system. It manages a user’s work on an individual drill. It helps ensure that we send the right messages in the right order and that we correctly grade users’ responses. The dialog context does not know much outside of the current drill. I.e., it doesn’t know what other drills the user has started or finished. The Drill Progress context is responsible for that.

The Dialog Context accepts **commands** and produces **events**. A command is a request to do something and an event is a record that something has occurred. Commands are written into a kinesis stream and processed in order. Events are written to a DynamoDB table that feeds a DynamoDB stream.

There are three commands:

* Process SMS Message (triggered by the SMS context).
* Trigger reminder to complete a drill (triggered from within the Drill Progress context).
* Trigger drill start (triggered from within the Drill Progress context).

The Dialog Context produces zero or more events in response to each command. The events are

* `DRILL_STARTED`
* `REMINDER_TRIGGERED`
* `USER_VALIDATED`
* `USER_VALIDATION_FAILED`
* `COMPLETED_PROMPT`
* `FAILED_PROMPT`
* `ADVANCED_TO_NEXT_PROMPT`
* `DRILL_COMPLETED`
* `NEXT_DRILL_REQUESTED`
* `OPTED_OUT`

These events are the source of truth for the system, both within the Dialog Context and for other contexts. They are consumed in three places:

* Within the dialog core, the events are used to derive a dialog state object.
* Within the SMS context, we use dialog events (consumed via a DynamoDB stream) to send messages.
* Within the Drill Progress context, we use dialog events (consumed via a DynamoDB stream) to update a user’s progress across drills.

## Consistency and Ordering

The dialog events are the source of truth for the entire system. If dialog state or drill progress ever become corrupt, we can rebuild them from the dialog events. But we’ll only get accurate results if we process the dialog events in order. So we’ve taken care to make sure that we always process events in order for each user.

How we maintain ordering and consistency:

* **Stream partitioning**
    * **The command stream is partitioned by phone number**, and each partition has only one consuming lambda. That ensures that we don’t process two commands for one phone number at the same time.
    * **DynamoDB tables are partitioned by phone number.** We rely on dynamoDB streams to propagate events to other contexts. Each stream partition has only one consuming lambda. That guarantees that each phone number’s events are processed in order.
* **Event batching**
    * **All events produced by a single command are persisted together in one “event batch” item in DynamoDB.** Each command can produce multiple events. E.g., `PROMPT_COMPLETED` and `ADVANCED_TO_NEXT_PROMPT` is a common combination. We found that when we persisted events individually, without batching, that we couldn’t guarantee the order that one command’s events would appear in the stream.
    * **Each event batch is tagged with a sequence number.** The sequence number is carried forward from the kinesis command stream. Each event batch is tagged with the sequence number of the command that produced the batch. Downstream consumers can use the sequence number to ensure that they don’t update based on old events.
* **Each command results in one DynamoDB transaction that both updates the dialog state and writes a dialog event batch.** It’s a simple way to ensure that our state and our events are in sync.
* **Drill content doesn’t change while the user is in the middle of a drill.** When a user starts a drill, we take a snapshot of the drill and store it in dialog state. That snapshot stays in the user’s dialog state until the drill is complete. So modifications to a drill’s content won’t lead to a jarring experience for users who are in the middle of that drill.

## Components

* 1 [lambda](../stopcovid/dialog/aws_lambdas/handle_command.py) that processes commands from the Kinesis stream
* The Kinesis stream itself
* DynamoDB tables for dialog state and events, the latter of which has a DynamoDB stream.