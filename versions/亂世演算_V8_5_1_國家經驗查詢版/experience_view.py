"""由可讀戰略 Q 報表擷取指定國家，避免同名局部比對誤選。"""

import re


COUNTRY_HEADER = re.compile(r"^國家：([^｜\r\n]+)(?:｜|$)", re.MULTILINE)


def extract_country_experience(report, names):
    targets = {str(name).strip() for name in names if str(name).strip()}
    headers = list(COUNTRY_HEADER.finditer(report))
    for index, match in enumerate(headers):
        if match.group(1).strip() not in targets:
            continue
        end = headers[index + 1].start() if index + 1 < len(headers) else len(report)
        return report[match.start():end].strip()
    return None
