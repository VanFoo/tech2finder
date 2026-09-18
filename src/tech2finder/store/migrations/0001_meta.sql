-- Small key/value table for facts about the store itself.
--
-- Its first real use is recording the md5sum of the imported SDE dump, so a
-- later import can ask "has the SDE changed?" by fetching a few bytes rather
-- than re-downloading 136 MB.
CREATE TABLE meta (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);
