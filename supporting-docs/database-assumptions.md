# Below lists all the restrictive assumptions made when designing the database schema (that enforce some type of rule)
- Students can enrol in a session at most once (they cannot be listed down more than once for a single session (eg. JPC Tuesday 4:30-7:30pm))
- Caterers cater for an entire school, which means all sessions hosted at that school have the same caterer
- Sessions only run on weekdays (Monday–Friday); the `day_of_week` enum does not include Saturday or Sunday
- Year levels are integers only (e.g. 9, 10, 11, 12); the schema cannot represent letter-based years such as Prep or Kindy so it does not support primary schools that use them
