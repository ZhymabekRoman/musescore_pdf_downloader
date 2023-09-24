import re
from urllib.parse import urlsplit


def URLValidator(url):
    """
    Проверяет, правильный/корректный ли URL адресс
    Args:
        url: Принимает URL адресс
    Return:
        False: Если URL не корректный
        True: Если URL корректный
    """
    # Код взят от сюда: https://github.com/django/django/blob/master/django/core/validators.py

    ul = '\u00a1-\uffff'  # Unicode letters range (must not be a raw string).

    # IP patterns
    ipv4_re = r'(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ipv6_re = r'\[[0-9a-f:.]+\]'  # (simple regex, validated later)

    # Host patterns
    hostname_re = r'[a-z' + ul + r'0-9](?:[a-z' + ul + r'0-9-]{0,61}[a-z' + ul + r'0-9])?'
    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_re = r'(?:\.(?!-)[a-z' + ul + r'0-9-]{1,63}(?<!-))*'

    tld_re = (
        r'\.'                                # dot
        r'(?!-)'                             # can't start with a dash
        r'(?:[a-z' + ul + '-]{2,63}'         # domain label
        r'|xn--[a-z0-9]{1,59})'              # or punycode label
        r'(?<!-)'                            # can't end with a dash
        r'\.?'                               # may have a trailing dot
    )
    host_re = '(' + hostname_re + domain_re + tld_re + '|localhost)'

    regex = re.compile(
        r'^(?:[a-z0-9.+-]*)://'  # scheme is validated separately
        r'(?:[^\s:@/]+(?::[^\s:@/]*)?@)?'  # user:pass authentication
        r'(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
        r'(?::\d{2,5})?'  # port
        r'(?:[/?#][^\s]*)?'  # resource path
        r'\Z', re.IGNORECASE)

    url_check_re = re.match(regex, url) is not None

    if not url_check_re:
        return False

    schemes = ['http', 'https']
    scheme = url.split('://')[0].lower()

    if scheme not in schemes:
        return False

    if len(urlsplit(url).hostname) > 253:
        return False

    return True
