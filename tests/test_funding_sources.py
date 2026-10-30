import json
from unittest.mock import Mock
import pytest
from scrapers.common.funding_sources import canonical, save, html_links, ted_search, cordis_csv

def test_canonical_schema():
    row=canonical('interreg_calls','https://interreg.eu/calls-for-projects/','A call')
    for field in ('id','title','source','url','summary','deadline','match_score','matched_keywords','scraped_at'):
        assert field in row
    assert row['match_score'] is None

def test_save_contract(tmp_path):
    row=canonical('eufunds_bg','https://www.eufunds.bg/test','Call 1')
    path=save('eufunds_bg',[row,row],tmp_path)
    payload=json.loads(path.read_text(encoding='utf8'))
    assert payload['count']==1 and len(payload['matches'])==1

def test_html_discovery_without_network():
    session=Mock()
    response=Mock(); response.text='<a href="/calls/one">Open funding programme 2026</a><a href="https://evil.test">Funding programme</a>'
    response.status_code=200; response.raise_for_status.return_value=None
    session.get.return_value=response
    out=html_links('interreg_calls',['https://interreg.eu/calls-for-projects/'],session=session,strict_robots=False,delay=0)
    assert len(out)==1 and out[0]['url']=='https://interreg.eu/calls/one'

def test_ted_api_contract():
    response=Mock(); response.json.return_value={'notices':[{'publication-number':'123456-2026','notice-title':'Solar panels'}]}
    response.raise_for_status.return_value=None
    session=Mock();session.post.return_value=response
    items=ted_search(session=session,query='PD >= 20261001')
    assert items[0]['call_identifier']=='123456-2026'
    assert session.post.call_args.kwargs['json']['query']=='PD >= 20261001'

def test_cordis_csv_contract():
    response=Mock(); response.content=b'id,title,objective\n1234,Project Alpha,Research\n'
    response.raise_for_status.return_value=None
    session=Mock();session.get.return_value=response
    items=cordis_csv('https://cordis.europa.eu/data.csv',session=session)
    assert items[0]['url']=='https://cordis.europa.eu/project/id/1234'

def test_cordis_rejects_untrusted_domain():
    with pytest.raises(ValueError):cordis_csv('https://malicious.example/f.csv')
