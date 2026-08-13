from typing import Dict


class SEOAgent:
    def optimize(self, script: Dict, research: Dict) -> Dict:
        title = script.get('title', 'Islamic Video')
        description = script.get('description', '')
        tags = script.get('tags', [])
        hashtags = script.get('hashtags', [])

        if len(title) > 60:
            title = title[:57] + '...'

        keywords = research.get('keywords', [])
        if keywords and description:
            keyword_section = '\n\n' + ' '.join(f'#{k}' for k in keywords[:5])
            if keyword_section not in description:
                description += keyword_section

        description += '\n\n🕌 Subscribe for more daily Islamic content!'

        return {"title": title, "description": description, "tags": tags[:15],
                "hashtags": hashtags, "keywords": keywords}
