You are an expert in extracting temporal relations from clinical texts according to the PRISM Annotation Guidelines v8.

The following text contains medical entities annotated inline in TANL format.
Annotation format: [text | entity_type(attribute) | entity_ID]

Attribute abbreviations:
  certainty: (+)=positive, (-)=negative, (?)=suspicious, (*)=general
  state: (+)=executed, (-)=negated, (予)=scheduled, (他)=other
  TIMEX3 type: (DATE) date, (TIME) time/now, (DUR) duration, (SET) frequency,
               (AGE) age, (MED) post-operative and other medical time expressions, (MISC) other

Your task is to identify temporal relations between entities and TIMEX3 expressions.

## Time Relation Types
- timeOn: E_from happened at the time of E_to. "December 19, 2024 CT" → CT was performed on that date.
- timeBefore: E_from ended before the time of E_to. Events in past medical history.
- timeAfter: E_from started after the time of E_to. Future scheduled events.
- timeBegin: E_from began at the time of E_to. "Started from April 23" → began at that time.
- timeEnd: E_from ended at the time of E_to. "Ended on May 7" → ended at that time.

Direction: event entity → TIMEX3 (E_to must be a TIMEX3 entity)
Time relations between TIMEX3 entities are also permitted (e.g., relative → absolute: [post-operative | TIMEX3(MED)] → [July 2008 | TIMEX3(DATE)]).

## state Attribute and Time Relation Interpretation
- state=scheduled + timeOn: scheduled to be executed at that time (e.g., "CT scheduled tomorrow")
- state=scheduled + timeBegin: scheduled to start at that time
- state=scheduled + timeAfter: scheduled to be executed after that time
- state=executed + timeOn: executed at that time
- state=executed + timeBefore: executed before that time
- state=executed + timeBegin: started at that time
- state=executed + timeEnd: ended at that time
- state=negated + timeOn: was not executed at that time
- state=negated + timeEnd: was being administered but stopped at that time

## TIMEX3 type=MED Handling
"Post-operative", "post-resection", "post-treatment" represent a limited period after surgery where effects persist.
- Mentioned as past medical history (effects no longer present) → timeBefore
- Currently under its influence → timeOn
Example: "Post-treatment pancreatitis suspected, currently under treatment" → timeOn for both "post-treatment" and "currently"

## changeRef Exclusivity
When a basic relation changeRef applies (e.g., "no remarkable changes since September 2003"), do NOT also assign a timeAfter to the same pair.

## Output Format
relation_type: eX -> eY (one relation per line)
If no relations exist, output only "(none)".

## Rules
- Use only entity IDs that appear in the annotated text
- Output ALL temporal relations without omission
- Output nothing other than the relations
