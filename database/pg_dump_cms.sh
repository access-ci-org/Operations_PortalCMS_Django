#!/bin/bash

DATE=`date +'%s'`
FILE=dump/cms2.dump.${DATE}
echo "pg_dump to: ${FILE}"

pg_dump -a -p 5434 -U portalcms_django \
    -t cms.availability -t cms.site -t cms.staff -t cms.support \
    -t cms.service -t cms.host -t cms.link -t cms.logentry \
    -t cms.event -t cms.hosteventlog -t cms.hosteventstatus \
    cms2 >${FILE}
echo "Dump complete."
echo "Manually execute:"
echo "DROP OWNED BY portalcms_django;"
echo "CREATE SCHEMA cms AUTHORIZATION portalcms_django;"