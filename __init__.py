from __future__ import unicode_literals, division, absolute_import, print_function

import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
from itertools import chain
from datetime import datetime

from calibre import random_user_agent
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.sources.base import Source

class Nhentai(Source):

    # Plugin Description
    name                = 'nhentai.net'
    description         = 'Pull data from nhentai.net, by name or by id'
    author              = 'Baduserrr'
    version             = (1, 0, 0)
    minimum_calibre_version = (2, 0, 0)

    capabilities = frozenset(['identify'])
    touched_fields = frozenset(['authors', 'identifier:nhentai', 'publisher', 'pubdate', 'tags', 'series', 'languages'])

    # -------------------------
    # Set constant variable
    NH_ID = 'nhentai'
    NH_URL = 'https://nhentai.net/g/'
    NH_QRY = 'https://nhentai.net/search?q='

    # -------------------------
    # Main stuff happen here
    def identify(self, log, result_queue, abort, title, authors, identifiers={}, timeout=30):
        gallery_id = identifiers.get(Nhentai.NH_ID, None)
        temp_raw_metadata = []
        if gallery_id:
            temp_raw_metadata.append(Nhentai.nhentai_metadata(gallery_id))
        else:
            search_name = urllib.parse.quote_plus(title)
            url = f"{Nhentai.NH_QRY}{search_name}"
            search_lang_result = Nhentai.nhentai_search(url)
            if search_lang_result:
                for temp_gallery_id in search_lang_result:
                    temp_raw_metadata.append(Nhentai.nhentai_metadata(temp_gallery_id))
            else:
                log.info(f"No search lang_result for | {title} | try to get the id")
        # log.info(f"Query = {temp_raw_metadata}")
        
        clean_metadata = []
        for raw_metadata in temp_raw_metadata:
            processed_metadata = {
                'title': ' '.join(raw_metadata.get('title', [])),
                'authors': Nhentai.get_authors(
                    raw_metadata.get('author', []),
                    raw_metadata.get('artist', [])
                    ),
                'identifiers': ' '.join(raw_metadata.get('identifier', [])),
                'publisher': ' '.join(raw_metadata.get('groups', [])),
                'pubdate': datetime.strptime(raw_metadata['uploaded'][0], "%Y-%m-%d").date() if raw_metadata.get('uploaded') else None,
                'language': Nhentai.get_language(raw_metadata.get('languages', [])),
                'tags': list(chain.from_iterable([
                    raw_metadata.get('parodies', []),
                    raw_metadata.get('characters', []),
                    raw_metadata.get('tags', []),
                    raw_metadata.get('categories', [])
                    ])),
            }
            clean_metadata.append(processed_metadata)

        log.info(f"Cleaned Data : {clean_metadata}")
        for cleaned in clean_metadata:
            mi = Metadata(title, cleaned['authors'])
            mi.set_identifier(Nhentai.NH_ID, cleaned['identifiers'])
            mi.publisher = cleaned['publisher']
            mi.pubdate = cleaned['pubdate']
            mi.language = cleaned['language']
            mi.tags = cleaned['tags']

            result_queue.put(mi)

    # -------------------------
    # Get html data of the link
    def get_html(url):
        ua = {
            "User-Agent": random_user_agent()
        }

        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode("utf-8")

        return html

    # -------------------------
    # if theres no gallery id, it will search the title, then get the id
    def nhentai_search(query):
        soup = BeautifulSoup(Nhentai.get_html(query), 'html.parser')

        temp_lang_result = []
        for a in soup.find('div', class_='container').find_all('a', class_='cover'):
            b = (re.search(r'/g/(\d+)/', (a['href']))).group(1)
            temp_lang_result.append(b)
        return(temp_lang_result)

    # -------------------------   
    # this is the metadata grabber, main shit
    def nhentai_metadata(gallery_id):
        url = f"{Nhentai.NH_URL}{gallery_id}"
        soup = BeautifulSoup(Nhentai.get_html(url), 'html.parser')

        title_check = []
        tags_list = ['parodies','characters','tags','artist','groups','languages','categories','pages', 'uploaded']

        for a in soup.find('h1', class_='title').find_all('span'):
            if hasattr(a, 'string') and a.string:
                title_check.append(a.string)
            else:
                title_check.append("")

        full_name = " ".join(part for part in title_check if part)
        strip_name = Nhentai.get_name(full_name)

        nhentai_metadata = {
            "author" : [strip_name['author']],
            "title" : [strip_name['full_title']],
            "identifier" : [gallery_id]
        }

        for a in tags_list:
            nhentai_metadata[a] = []

        # Get tags section loop all of it
        for a in (soup.find('section', id='tags')).find_all('div', class_='tag-container'):
            b = a.contents[0].strip()
            for c in tags_list:
                if c in b.lower():
                    if c == 'uploaded':
                        time = a.find('time')['datetime'][:10]
                        nhentai_metadata[c].append(time)
                    else:
                        names = a.find_all('span', class_='name')
                        for name in names:
                            nhentai_metadata[c].append(name.text)

        return nhentai_metadata

    # -------------------------
    # split the file name
    def get_name(filename):
        match = re.match(r'^(\([^)]+\)\s*)?\[([^\]]+)\]\s+(.+)', filename)

        if match:
            prefix = match.group(1).strip() if match.group(1) else ""
            author = match.group(2).strip()
            title = match.group(3).strip()
            full_title = f"{prefix} {title}".strip()
            return {
                'author': author,
                'full_title': full_title
            }
        else:
            return None
            
    # -------------------------
    # combine authors and artist name
    def get_authors(authors, artists):
        authors = [a.strip() for a in authors or [] if a.strip()]
        artists = [a.strip() for a in artists or [] if a.strip()]

        temp_author = ' '.join(authors).lower()

        # Only include artists not already mentioned in any form in author entries
        temp_artist = [
            artist for artist in artists
            if artist.lower() not in temp_author
        ]

        return authors + temp_artist
    
    # -------------------------
    # combine authors and artist name
    def get_language(raw_languages, default='und'):
        lang_list = {
            'english': 'eng',
            'japanese': 'jpn',
            'chinese': 'chi',
            'indonesian': 'ind',
            'korean': 'kor',
            'spanish': 'spa',
        }

        if not raw_languages:
            return default
        else:
            lang_result = []
            for lang in raw_languages:
                key = lang.lower().strip()
                if key != 'translated' and key in lang_list:
                    lang_result.append(lang_list[key])

        return lang_list[key] if lang_list[key] else [default]