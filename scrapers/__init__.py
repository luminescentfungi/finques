"""
scrapers package – registry of all scraper classes.
"""

from scrapers.shbarcelona      import SHBarcelonaScraper
from scrapers.tecnocasa        import TecnocasaScraper
from scrapers.housfy           import HoushfyScraper
from scrapers.borsalloguers    import BorsalloguersScraper
from scrapers.finquesteixidor  import FinquesTeixidorScraper
from scrapers.finquescampanya  import FinquesCampanyaScraper
from scrapers.finquesbou       import FinquesBouScraper
from scrapers.onixrenta        import OnixRentaScraper
from scrapers.dianafinques     import DianaFinquesScraper
from scrapers.habitabarcelona  import HabitaBarcelonaScraper
from scrapers.monapart         import MonapartScraper
from scrapers.donpiso          import DonPisoScraper
from scrapers.grocasa          import GrocasaScraper
from scrapers.remax            import RemaxScraper
from scrapers.century21        import Century21Scraper
from scrapers.myspotbarcelona  import MySpotBarcelonaScraper
from scrapers.locabarcelona    import LocaBarcelonaScraper
from scrapers.habitaclia       import HabitacliaScraper
from scrapers.gilamargos       import GilAmargósScraper
from scrapers.fincaseva        import FincasEvaScraper
from scrapers.selektaproperties import SelektaPropertiesScraper
from scrapers.casablau         import CasaBlauScraper
from scrapers.finquesmarba     import FinquesMarbasScraper
from scrapers.immobarcelo      import ImmoBarceloScraper

# Ordered registry: scraper_name -> scraper_class
ALL_SCRAPERS = {
    s.name: s for s in [
        SHBarcelonaScraper,
        TecnocasaScraper,
        HoushfyScraper,
        BorsalloguersScraper,
        FinquesTeixidorScraper,
        FinquesCampanyaScraper,
        FinquesBouScraper,
        OnixRentaScraper,
        DianaFinquesScraper,
        HabitaBarcelonaScraper,
        MonapartScraper,
        DonPisoScraper,
        GrocasaScraper,
        RemaxScraper,
        Century21Scraper,
        MySpotBarcelonaScraper,
        LocaBarcelonaScraper,
        HabitacliaScraper,
        GilAmargósScraper,
        FincasEvaScraper,
        SelektaPropertiesScraper,
        CasaBlauScraper,
        FinquesMarbasScraper,
        ImmoBarceloScraper,
    ]
}

__all__ = ["ALL_SCRAPERS"]
