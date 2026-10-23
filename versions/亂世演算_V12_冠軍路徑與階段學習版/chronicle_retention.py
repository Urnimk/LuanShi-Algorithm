"""Keep only the latest 50 generations, with constant-size all-time records."""
from pathlib import Path
import shutil

GENERATION_LIMIT = 50


def trim(country, limit=GENERATION_LIMIT):
    history=country.get('country_chronicle')
    if not isinstance(history,list) or len(history)<=limit:
        return 0
    def generation(item,index):
        try:return int(item.get('generation',index+1))
        except (TypeError,ValueError,AttributeError):return index+1
    generations={generation(item,i) for i,item in enumerate(history) if isinstance(item,dict)}
    if len(generations)<=limit:return 0
    keep=set(sorted(generations,reverse=True)[:limit])
    records=country.setdefault('chronicle_all_time',{})
    for item in history:
        if not isinstance(item,dict):continue
        power=max(0,int(item.get('peak_power',0) or 0))
        if power>int(records.get('peak_power',0) or 0):
            records.update(peak_power=power,peak_power_year=item.get('peak_power_year'))
        records['peak_population']=max(int(records.get('peak_population',0) or 0),
                                       int(item.get('peak_population',0) or 0))
        rank=item.get('best_rank')
        if rank not in (None,'',0):
            records['best_rank']=min(int(records.get('best_rank') or rank),int(rank))
    old=len(history)
    history[:]=[item for i,item in enumerate(history) if isinstance(item,dict) and generation(item,i) in keep]
    country['chronicle_removed_generations']=int(country.get('chronicle_removed_generations',0) or 0)+len(generations-keep)
    return old-len(history)


def remove_report_data(saves_directory):
    """User explicitly requested removing the retired report's disk footprint.
    Remove only its dedicated directory; never follow a symlink to another tree.
    """
    target=Path(saves_directory)/'country_history'
    if target.is_symlink():target.unlink();return True
    if target.is_dir():shutil.rmtree(target);return True
    return False
