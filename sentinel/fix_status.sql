-- Fix files showing as stopped that have annotated videos (should be saved)
UPDATE core_mediafile 
SET status = 'saved' 
WHERE status = 'stopped' 
AND annotated_video IS NOT NULL 
AND annotated_video != '';

-- Update all processed to saved
UPDATE core_mediafile 
SET status = 'saved' 
WHERE status = 'processed';

-- Show results
SELECT id, filename, status FROM core_mediafile;
