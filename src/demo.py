"""Demo data generator — realistic brand review data for offline demonstration.

Provides pre-built review sets for 4 brands that showcase the full scoring engine:
  - Nike (strong consumer brand, public company)
  - Chanel (luxury, strong heritage)
  - Tesla (polarizing, high momentum)
  - Gap (struggling, declining)

Each brand gets ~80-120 reviews spread across sources (reddit, google_news,
google_trends, wikipedia, resale) with realistic text, timestamps, ratings,
and engagement levels. This exercises every dimension of the scoring engine.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from src.models.brand import Brand
from src.models.review import Review, ReviewCollection


# ───────────────────────────────────────────────────────────────────────────
# Brand definitions
# ───────────────────────────────────────────────────────────────────────────

DEMO_BRANDS = {
    "Nike": Brand(
        name="Nike",
        ticker="NKE",
        search_terms=["Nike", "Nike Inc"],
        wikipedia_article="Nike,_Inc.",
        subreddits=["Nike", "sneakers"],
        competitors=["Adidas", "New Balance"],
        category="sportswear",
    ),
    "Chanel": Brand(
        name="Chanel",
        search_terms=["Chanel", "Chanel fashion"],
        wikipedia_article="Chanel",
        subreddits=["luxury", "fashion"],
        competitors=["Dior", "Louis Vuitton"],
        category="luxury",
    ),
    "Tesla": Brand(
        name="Tesla",
        ticker="TSLA",
        search_terms=["Tesla", "Tesla Motors"],
        wikipedia_article="Tesla,_Inc.",
        subreddits=["teslamotors", "electricvehicles"],
        competitors=["Rivian", "Ford"],
        category="automotive",
    ),
    "Gap": Brand(
        name="Gap",
        ticker="GAP",
        search_terms=["Gap", "Gap Inc"],
        wikipedia_article="Gap_Inc.",
        subreddits=["fashion", "malefashionadvice"],
        competitors=["H&M", "Zara"],
        category="retail",
    ),
}


# ───────────────────────────────────────────────────────────────────────────
# Review templates by brand profile
# ───────────────────────────────────────────────────────────────────────────

_NIKE_REVIEWS = {
    "reddit": [
        ("Just copped the new Air Max 90s and they are absolutely incredible. Best sneaker release this year, highly recommend for anyone on the fence.", 4.5, 342),
        ("Nike quality has been declining lately. My last three pairs all had glue issues within 2 months. Would not recommend at these prices anymore.", 2.0, 187),
        ("The Nike app is honestly game changer for drops. Got early access to the Dunks and they sold out in 30 seconds on SNKRS.", 4.0, 256),
        ("Been a loyal Nike customer for 15 years. Their running shoes are consistently the best bang for your buck. Can't recommend enough.", 5.0, 98),
        ("Hot take: New Balance is making better lifestyle sneakers than Nike right now. Nike needs to stop with the boring colorways.", 2.5, 445),
        ("Nike's sustainability push is real. The Move to Zero line uses recycled materials and they actually feel premium. Love this direction.", 4.5, 167),
        ("Tried returning defective shoes and Nike customer service was fantastic. Full refund and 20% off next order. Top notch support.", 4.0, 89),
        ("The Vaporfly changed my running game. Shaved 3 minutes off my marathon time. Worth every penny of the $250 price tag.", 5.0, 312),
        ("Nike's collaboration with Off-White is still iconic even after Virgil. These limited edition pieces are investment pieces.", 4.5, 523),
        ("Am I the only one who thinks Nike is overpriced for what it is? Adidas ultraboost is better quality for less money.", 2.0, 234),
        ("Just visited the Nike flagship in NYC - blew my mind. The customization station alone is worth the trip. Game-changer retail experience.", 4.5, 156),
        ("Nike earnings report looks solid. Revenue up 8% YoY. Their DTC strategy is clearly working. Bullish on NKE.", 4.0, 67),
        ("Been using Nike Training Club app for 6 months. Completely replaced my gym membership. Best free fitness content out there.", 5.0, 201),
        ("Nike's latest campaign featuring local athletes is incredible. They get marketing like nobody else in sportswear.", 4.0, 134),
        ("Quality control issues seem to be getting worse. Third pair this year with manufacturing defects. Starting to look elsewhere.", 1.5, 289),
    ],
    "google_news": [
        ("Nike reports strong Q3 earnings beating analyst expectations with revenue growth of 8.2%", 4.5, 0),
        ("Nike announces expansion of sustainable manufacturing initiative across 200 factories", 4.0, 0),
        ("Nike stock rises 3.5% after announcing new partnership with major tech company", 4.0, 0),
        ("Consumer sentiment for Nike rebounds as new product line receives positive reviews", 4.0, 0),
        ("Nike faces criticism over labor practices in Southeast Asian suppliers", 2.0, 0),
        ("Nike launches innovative recycled materials sneaker line to positive reception", 4.5, 0),
        ("Nike digital sales surge 24% year-over-year driven by app engagement", 4.5, 0),
        ("Analysts upgrade Nike stock citing improved margins and strong brand momentum", 4.5, 0),
        ("Nike invests $150M in next-gen athlete performance technology center", 4.0, 0),
        ("Nike vs Adidas: market share battle intensifies in North American sportswear", 3.5, 0),
    ],
    "google_trends": [
        ("Nike Air Max trending search interest spike 78/100", None, 78),
        ("Nike SNKRS app search volume at 85/100", None, 85),
        ("Nike sustainability search interest rising to 62/100", None, 62),
        ("Nike outlet search steady at 71/100", None, 71),
        ("Nike stock search volume at 55/100", None, 55),
    ],
    "wikipedia": [
        ("Nike Inc daily pageviews averaging 45000 over past 30 days, trending upward", None, 45000),
        ("Nike Inc pageview spike during earnings week reaching 72000 daily views", None, 72000),
        ("Nike Inc pageviews stable at above-average levels indicating sustained interest", None, 35000),
    ],
}

_CHANEL_REVIEWS = {
    "reddit": [
        ("Just got my first Chanel Classic Flap and it is a dream brand bag. The craftsmanship is absolutely unreal. This is a forever piece and investment piece.", 5.0, 567),
        ("Chanel price increases are getting insane. Classic Flap was $5800 in 2019, now it's $10800. Not worth the investment anymore.", 2.5, 890),
        ("The heritage and tradition behind Chanel is unmatched. Founded by Coco herself, the maison's legacy lives on. Timeless and iconic.", 5.0, 234),
        ("Picked up a rare limited edition Chanel Boy bag. Already worth more than retail on Vestiaire. These bags are collectible investments.", 5.0, 445),
        ("Chanel beauty is honestly underrated. Their lipsticks and skincare rival La Mer at half the price. Five stars across the board.", 4.5, 167),
        ("Hot take: Chanel has lost its exclusivity. Everyone and their mother has a Chanel bag now. It's too common and ubiquitous.", 2.0, 378),
        ("The Chanel Métiers d'Art collection this year was breathtaking. Artisan level handmade details. This is why luxury exists.", 5.0, 289),
        ("Bought a Chanel jacket secondhand on TheRealReal - still in perfect condition after 20 years. That's heirloom quality.", 5.0, 198),
        ("Chanel No. 5 is still iconic after 100+ years. No other fragrance house has that kind of heritage. Absolute grail brand.", 5.0, 156),
        ("I can't justify Chanel prices anymore. My friend's bag is already falling apart after 2 years. Quality has declined since Karl left.", 2.0, 512),
        ("Visited the Chanel boutique on Rue Cambon in Paris. The history, the staircase, the mirrors - it's a fashion pilgrimage. Obsessed.", 5.0, 234),
        ("Chanel resale values are holding strong. Classic Flap appreciated 70% over 5 years. Better than most stocks honestly.", 4.5, 345),
        ("Waiting list for the new Chanel 22 bag is 3 months. They're keeping it exclusive and I respect that.", 4.0, 123),
        ("Chanel made in France quality is just different. Swiss made movements in their watches too. Nothing else comes close.", 5.0, 267),
    ],
    "google_news": [
        ("Chanel reports record revenue exceeding $20 billion driven by leather goods and fragrance", 5.0, 0),
        ("Chanel raises prices again across handbag range amid strong demand", 3.5, 0),
        ("Chanel's Métiers d'Art show celebrates artisan craftsmanship heritage", 4.5, 0),
        ("Chanel invests in vertical integration acquiring high-end tanneries and textile mills", 4.0, 0),
        ("Luxury resale market shows Chanel bags appreciating faster than gold", 4.5, 0),
        ("Chanel Creative Director unveils new vision maintaining brand DNA while modernizing", 4.0, 0),
        ("Chanel remains world's most desirable luxury brand according to new survey", 5.0, 0),
        ("Chanel digital strategy expands with exclusive online experiences for VIP clients", 4.0, 0),
    ],
    "google_trends": [
        ("Chanel bag search interest at 88/100 near all-time high", None, 88),
        ("Chanel price increase search spiking to 92/100", None, 92),
        ("Chanel resale value search interest at 75/100", None, 75),
        ("Chanel perfume search steady at 80/100", None, 80),
    ],
    "wikipedia": [
        ("Chanel daily pageviews averaging 38000 stable high interest", None, 38000),
        ("Chanel pageviews spike during fashion week to 55000 daily", None, 55000),
    ],
    "resale": [
        ("Chanel Classic Flap Medium listed at $9200 on TheRealReal, retail $10800, resale ratio 0.85", 4.0, 0),
        ("Chanel Boy Bag sold for $6500, original retail $5900, appreciation of 10%", 4.5, 0),
        ("Chanel 2.55 Reissue trading at 95% of retail on Vestiaire Collective", 4.0, 0),
        ("Chanel vintage pieces commanding premium prices, some exceeding original retail by 200%", 5.0, 0),
        ("Chanel jewelry resale strong at 75-90% of retail value on Grailed", 4.0, 0),
    ],
}

_TESLA_REVIEWS = {
    "reddit": [
        ("Model 3 Performance is the best car I've ever owned. Acceleration is addictive and autopilot is game changer on highway.", 5.0, 678),
        ("Tesla service center experience was horrible. Waited 6 weeks for a simple repair. Never again with this company.", 1.0, 923),
        ("Elon's tweets are tanking the brand. Half my friends who were considering Tesla are now looking at Rivian instead.", 1.5, 1245),
        ("Just road tripped 2000 miles in my Model Y. Supercharger network is unbeatable. No range anxiety at all. Highly recommend.", 5.0, 456),
        ("FSD Beta is genuinely terrifying. Made three dangerous moves in one drive. This is not ready and people could get hurt.", 1.0, 1678),
        ("Tesla Model S Plaid did 0-60 in 1.99 seconds at the drag strip. Nothing else comes close for the price. Insane technology.", 5.0, 567),
        ("Build quality on my 2024 Model 3 Highland is actually great. Panel gaps are gone. Haters need to drive the new ones.", 4.5, 345),
        ("The Tesla community is incredible. Owners helping owners, sharing tips, evangelizing the mission. Part of my identity at this point.", 4.5, 234),
        ("Stock price is disconnected from reality. $800B market cap for a car company that sells 2M cars? Way overvalued.", 2.0, 890),
        ("Switched from BMW to Tesla and will buy again. Over-the-air updates keep making the car better. Revolutionary approach.", 5.0, 312),
        ("Paint quality is terrible for a $50K car. Already have chips and swirls after 3 months. Unacceptable at this price point.", 1.5, 445),
        ("Tesla Powerwall + Solar Roof changed my life. $0 electric bill and I'm charging my car for free. The ecosystem is brilliant.", 5.0, 567),
        ("Cybertruck is either the future or the ugliest vehicle ever made. I'm obsessed either way. Can't stop talking about it.", 4.0, 1890),
        ("Tesla insurance based on driving behavior is honestly fair. My premiums dropped 40% because I'm a safe driver.", 4.0, 123),
        ("Lost $30K on TSLA options this year. Everyone needs to know this stock is pure gambling at this point.", 1.0, 678),
    ],
    "google_news": [
        ("Tesla delivers record 500K vehicles in Q4 beating analyst expectations by 8%", 4.5, 0),
        ("Tesla stock volatile as Elon Musk controversies continue to impact brand sentiment", 2.0, 0),
        ("Tesla Supercharger network opens to all EVs marking major industry shift", 4.5, 0),
        ("Tesla Full Self-Driving under NHTSA investigation after series of incidents", 1.5, 0),
        ("Tesla energy division revenue surges 65% year-over-year on Megapack demand", 4.5, 0),
        ("Consumer Reports ranks Tesla reliability below industry average for third year", 2.0, 0),
        ("Tesla Cybertruck demand exceeds production capacity with 2-year waitlist", 4.0, 0),
        ("Tesla faces growing competition from Chinese EV makers BYD and NIO", 2.5, 0),
        ("Tesla announces next-gen affordable $25K vehicle targeting mass market", 4.5, 0),
        ("Musk's political activities causing measurable brand damage per new survey data", 1.5, 0),
    ],
    "google_trends": [
        ("Tesla search interest at 95/100 near all-time high volume", None, 95),
        ("Tesla stock search volume extremely high at 90/100", None, 90),
        ("Cybertruck search interest at 82/100 still elevated", None, 82),
        ("Tesla vs Rivian search trending upward at 68/100", None, 68),
        ("Tesla FSD search interest at 74/100", None, 74),
        ("Tesla problems search interest rising to 71/100", None, 71),
    ],
    "wikipedia": [
        ("Tesla Inc daily pageviews averaging 85000 highest among automakers", None, 85000),
        ("Tesla Inc pageview spike to 150000 during earnings and Musk news cycles", None, 150000),
        ("Tesla Inc consistently in top 50 most-viewed Wikipedia articles", None, 60000),
    ],
}

_GAP_REVIEWS = {
    "reddit": [
        ("Does anyone even shop at Gap anymore? Their stores are always empty. Feels like a brand from the 90s.", 2.0, 345),
        ("Gap quality has fallen off a cliff. T-shirts that used to last years now fall apart after 3 washes. Stay away.", 1.5, 234),
        ("Everything at Gap is permanently on sale. 40% off, 50% off, extra 20% on top. That's not a deal, that's desperation.", 2.0, 456),
        ("Picked up some Gap basics at the outlet for cheap. Fine for the price I guess but nothing special.", 3.0, 45),
        ("Gap's collaboration with Kanye was a disaster. Lost money and credibility. Management has no vision for this brand.", 1.0, 567),
        ("Old Navy is eating Gap alive from below while Uniqlo attacks from the side. What is Gap's identity anymore?", 2.0, 289),
        ("Remember when Gap was cool? Khakis campaign, celebrity ads. Now it's just another forgettable fast fashion brand.", 2.0, 178),
        ("Bought Gap jeans on sale for $20 and honestly they're decent. Not worth retail $60 though. Not worth the price at full.", 3.0, 67),
        ("Gap closing 350 stores tells you everything about this brand's trajectory. Declining fast.", 1.5, 389),
        ("Their kids line is still okay. Baby Gap has some cute stuff at reasonable prices. That's about all I'd recommend.", 3.0, 56),
        ("Gap stock is a value trap. Don't believe the cheap P/E ratio. This business is in structural decline.", 1.5, 234),
    ],
    "google_news": [
        ("Gap Inc announces closure of 150 additional stores amid declining foot traffic", 1.5, 0),
        ("Gap reports fourth consecutive quarter of same-store sales decline", 1.5, 0),
        ("Gap CEO resigns as turnaround strategy fails to gain traction", 1.0, 0),
        ("Gap explores strategic alternatives including potential sale of brand", 2.0, 0),
        ("Gap clearance sale sparks concerns about inventory management and brand health", 1.5, 0),
        ("Gap attempts brand refresh with new campaign but consumers remain skeptical", 2.5, 0),
        ("Analysts downgrade Gap stock citing accelerating market share loss", 1.5, 0),
    ],
    "google_trends": [
        ("Gap clothing search interest declining at 28/100 five-year low", None, 28),
        ("Gap sale search at 45/100 higher than brand search indicating discount dependency", None, 45),
        ("Gap store closing search trending at 38/100", None, 38),
    ],
    "wikipedia": [
        ("Gap Inc daily pageviews averaging 8000 well below category peers", None, 8000),
        ("Gap Inc pageviews declining trend over past 6 months", None, 5000),
    ],
}

_BRAND_REVIEWS = {
    "Nike": _NIKE_REVIEWS,
    "Chanel": _CHANEL_REVIEWS,
    "Tesla": _TESLA_REVIEWS,
    "Gap": _GAP_REVIEWS,
}


def get_demo_brand(name: str) -> Brand:
    """Get a pre-configured demo brand by name."""
    if name in DEMO_BRANDS:
        return DEMO_BRANDS[name]
    raise ValueError(
        f"Unknown demo brand '{name}'. Available: {', '.join(DEMO_BRANDS.keys())}"
    )


def list_demo_brands() -> list[str]:
    """Return available demo brand names."""
    return list(DEMO_BRANDS.keys())


def generate_demo_data(brand_name: str) -> dict[str, ReviewCollection]:
    """Generate realistic review collections for a demo brand.

    Returns a dict of source_name -> ReviewCollection, ready to be fed
    into the scoring pipeline.
    """
    if brand_name not in _BRAND_REVIEWS:
        raise ValueError(
            f"No demo data for '{brand_name}'. Available: {', '.join(_BRAND_REVIEWS.keys())}"
        )

    templates = _BRAND_REVIEWS[brand_name]
    now = datetime.utcnow()
    rng = random.Random(42)  # Deterministic for reproducibility

    collections: dict[str, ReviewCollection] = {}

    for source, review_tuples in templates.items():
        reviews = []
        for i, (text, rating, engagement) in enumerate(review_tuples):
            # Spread reviews over the past 90 days with some clustering
            days_ago = rng.uniform(0, 90)
            hours_offset = rng.uniform(0, 24)
            ts = now - timedelta(days=days_ago, hours=hours_offset)

            reviews.append(Review(
                text=text,
                source=source,
                timestamp=ts,
                rating=rating,
                engagement=engagement,
            ))

        collections[source] = ReviewCollection(
            brand_name=brand_name,
            reviews=reviews,
        )

    return collections


def generate_demo_competitors(brand_name: str) -> dict[str, ReviewCollection]:
    """Generate minimal competitor data for competitive position scoring."""
    brand = DEMO_BRANDS.get(brand_name)
    if not brand or not brand.competitors:
        return {}

    rng = random.Random(123)
    now = datetime.utcnow()
    competitors: dict[str, ReviewCollection] = {}

    # Simple competitor review profiles
    competitor_profiles = {
        "Adidas": (3.9, 0.15, "Good quality athletic wear. Ultraboost is comfortable."),
        "New Balance": (4.2, 0.25, "Amazing running shoes. Made in USA quality is worth the price."),
        "Dior": (4.6, 0.30, "Stunning luxury pieces. The craftsmanship is exceptional."),
        "Louis Vuitton": (4.3, 0.20, "Classic luxury brand. Monogram is iconic but everywhere now."),
        "Rivian": (4.1, 0.20, "R1T is the best adventure vehicle. Build quality is impressive."),
        "Ford": (3.5, 0.05, "F-150 Lightning is solid. Traditional reliability with EV benefits."),
        "H&M": (3.0, -0.10, "Cheap and trendy but quality is disposable. Fast fashion issues."),
        "Zara": (3.3, 0.05, "On-trend fast fashion. Better quality than H&M but still not great."),
    }

    for comp_name in brand.competitors:
        avg_rating, sentiment, template = competitor_profiles.get(
            comp_name, (3.5, 0.0, f"{comp_name} products are decent quality overall.")
        )
        reviews = []
        for i in range(15):
            days_ago = rng.uniform(0, 90)
            rating_jitter = rng.uniform(-0.5, 0.5)
            reviews.append(Review(
                text=f"{template} {'Highly recommend.' if i % 3 == 0 else 'Good value for the price.' if i % 3 == 1 else 'Could be better.'}",
                source="reddit",
                timestamp=now - timedelta(days=days_ago),
                rating=max(1.0, min(5.0, avg_rating + rating_jitter)),
                engagement=rng.randint(10, 200),
                sentiment_compound=sentiment + rng.uniform(-0.2, 0.2),
                sentiment_label="positive" if sentiment > 0 else "negative" if sentiment < -0.1 else "neutral",
            ))
        competitors[comp_name] = ReviewCollection(brand_name=comp_name, reviews=reviews)

    return competitors
