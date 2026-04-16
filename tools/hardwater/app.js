/**
 * app.js — Water Hardness Checker
 * Site   : oceansidehairsalon.com
 * Purpose: Client-side water hardness lookup via USGS live API chain.
 *          Falls back to a static regional database when the live chain fails.
 *          Results are cached in localStorage with a 7-day TTL.
 *
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  EXECUTION FLOW  checkWaterHardness(zipCode)                            │
 * │  1. Check localStorage cache → render immediately if hit, stop.         │
 * │  2. Nominatim geocoding:   ZIP → { lat, lon }                           │
 * │  3. USGS site search:      nearest water quality station (15-mi radius) │
 * │  4. USGS daily values:     latest hardness reading (parameterCd=00900)  │
 * │  5. Cache result → render                                               │
 * │  [FALLBACK] If steps 2–4 fail → nearest city from waterHardnessData     │
 * └─────────────────────────────────────────────────────────────────────────┘
 */

(function () {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════════
  // CONSTANTS
  // ═══════════════════════════════════════════════════════════════════════════

  const CACHE_PREFIX = 'water_data_';
  const CACHE_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000; // 7-day TTL
  const PROXY_URL = 'https://water-api-helper.mok243643.workers.dev/?url=';
  const API = {
    NOMINATIM: 'https://nominatim.openstreetmap.org/search',
    USGS_SITE: 'https://waterservices.usgs.gov/nwis/site/',
    USGS_DV: 'https://waterservices.usgs.gov/nwis/dv/',
  };

  // Loading step labels (shown during API chain execution)
  const LOAD_STEPS = [
    { icon: '📍', text: 'Resolving ZIP code location…' },
    { icon: '🔬', text: 'Locating nearby water quality stations…' },
    { icon: '💧', text: 'Reading hardness measurements (USGS)…' },
  ];

  // ═══════════════════════════════════════════════════════════════════════════
  // AFFILIATE PRODUCT CATALOGUE  (hair-care niche, four urgency tiers)
  // Keys: 'low' | 'moderate' | 'high' | 'critical'
  // Update URLs with your Amazon Associates tag: oceansidehair-20
  // ═══════════════════════════════════════════════════════════════════════════

  const PRODUCTS = {
    low: [
      {
        icon: '🚿', tag: 'Preventive Care',
        name: 'AquaBliss High Output Shower Filter',
        desc: 'Even soft water carries trace chlorine that strips natural oils. A shower filter is a simple, high-ROI upgrade for any hair type.',
        url: 'https://www.amazon.com/s?k=shower+filter+hair+care&tag=oceansidehair-20',
        tagColor: '#4CAF50',
      },
      {
        icon: '🧴', tag: 'Daily Maintenance Shampoo',
        name: 'Kristin Ess Scalp Purifying Micellar Shampoo',
        desc: 'Gentle micellar formula that lifts oil and residue without disturbing your hair\'s natural moisture balance.',
        url: 'https://amzn.to/461Gx9S',
        tagColor: '#4CAF50',
      },
    ],
    moderate: [
      {
        icon: '🧴', tag: 'Use 1–2× Per Week',
        name: 'Ion Hard Water Shampoo',
        desc: 'Affordable EDTA-based chelating shampoo. Gentle enough for frequent use; powerful enough to clear moderate mineral deposits before they compound.',
        url: 'https://amzn.to/49LqXR3',
        tagColor: '#8BC34A',
      },
      {
        icon: '🚿', tag: 'Shower Filter — Recommended',
        name: 'Vitamin C Shower Filter',
        desc: 'Intercepts minerals and chlorine before they touch your hair. Works synergistically alongside chelating shampoo for compounding benefits.',
        url: 'https://www.amazon.com/s?k=vitamin+c+shower+filter+hair&tag=oceansidehair-20',
        tagColor: '#8BC34A',
      },
    ],
    high: [
      {
        icon: '⭐', tag: '★ Top Pick — Use 2–3× / Week',
        name: 'Malibu C Hard Water Wellness Shampoo',
        desc: 'Vitamin C–powered chelating formula clinically shown to lift calcium and magnesium deposits from hair without stripping color. The benchmark for hard water areas.',
        url: 'https://www.amazon.com/dp/B01N23J5C1?tag=oceansidehair-20',
        tagColor: '#e65100',
      },
      {
        icon: '💊', tag: 'Weekly Deep Reset',
        name: 'Kenra Clarifying Shampoo',
        desc: 'Professional-grade chelating + clarifying combination. Ideal once-weekly treatment to break up stubborn scale buildup and restore hair clarity.',
        url: 'https://amzn.to/4sPuG8L',
        tagColor: '#FFC107',
      },
      {
        icon: '🚿', tag: 'Shower Filter — Strongly Recommended',
        name: 'KDF + Vitamin C Dual-Stage Filter',
        desc: 'Dual-stage filter neutralises both chlorine and heavy minerals at the source — the highest-leverage upgrade for hard water hair health.',
        url: 'https://www.amazon.com/s?k=kdf+vitamin+c+shower+filter&tag=oceansidehair-20',
        tagColor: '#FFC107',
      },
    ],
    critical: [
      {
        icon: '⚠️', tag: '⚠ Use Every Wash',
        name: 'Malibu C Hard Water Wellness Shampoo',
        desc: 'The leading chelating shampoo for extremely hard water — Vitamin C formula dissolves even severe calcium and magnesium scale with every wash.',
        url: 'https://www.amazon.com/dp/B01N23J5C1?tag=oceansidehair-20',
        tagColor: '#F44336',
      },
      {
        icon: '💊', tag: 'Weekly Scalp Reset',
        name: 'Kenra Clarifying Shampoo',
        desc: 'Heavy-duty weekly treatment for long-standing mineral buildup. Pair with a daily chelating shampoo for a complete recovery protocol.',
        url: 'https://amzn.to/4sPuG8L',
        tagColor: '#F44336',
      },
      {
        icon: '✨', tag: 'Premium Salon-Grade Option',
        name: 'R+Co Oblivion Clarifying Shampoo',
        desc: 'When severity demands the strongest formula. Salon-quality chelating action with a luxury sensory experience designed for very hard water areas.',
        url: 'https://amzn.to/4pT2jEb',
        tagColor: '#c62828',
      },
      {
        icon: '🚿', tag: '⚠ Install This First',
        name: 'High-Output Vitamin C Shower Filter',
        desc: 'Non-negotiable at this hardness level. Dramatically reduces mineral load before water ever contacts your hair or scalp.',
        url: 'https://www.amazon.com/s?k=high+output+vitamin+c+shower+filter&tag=oceansidehair-20',
        tagColor: '#b71c1c',
      },
    ],
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // STATIC FALLBACK DATABASE
  //
  // Populated with all 50 US state averages and ~35 representative cities.
  // To extend coverage, copy additional entries from date.json into cities[].
  // Format: { city, state, lat, lng, ppm, gpg, zips: string[] }
  // ═══════════════════════════════════════════════════════════════════════════

  const waterHardnessData = {

    // ── All 50 state averages ──────────────────────────────────────────────
    stateAverages: {
      AL: { avg_ppm: 74, classification: 'Moderately Hard' },
      AK: { avg_ppm: 45, classification: 'Soft' },
      AZ: { avg_ppm: 290, classification: 'Very Hard' },
      AR: { avg_ppm: 64, classification: 'Moderately Hard' },
      CA: { avg_ppm: 249, classification: 'Very Hard' },
      CO: { avg_ppm: 127, classification: 'Hard' },
      CT: { avg_ppm: 50, classification: 'Soft' },
      DE: { avg_ppm: 117, classification: 'Moderately Hard' },
      FL: { avg_ppm: 216, classification: 'Very Hard' },
      GA: { avg_ppm: 56, classification: 'Soft' },
      HI: { avg_ppm: 90, classification: 'Moderately Hard' },
      ID: { avg_ppm: 230, classification: 'Very Hard' },
      IL: { avg_ppm: 347, classification: 'Very Hard' },
      IN: { avg_ppm: 363, classification: 'Very Hard' },
      IA: { avg_ppm: 299, classification: 'Very Hard' },
      KS: { avg_ppm: 266, classification: 'Very Hard' },
      KY: { avg_ppm: 153, classification: 'Hard' },
      LA: { avg_ppm: 97, classification: 'Moderately Hard' },
      ME: { avg_ppm: 21, classification: 'Soft' },
      MD: { avg_ppm: 106, classification: 'Moderately Hard' },
      MA: { avg_ppm: 34, classification: 'Soft' },
      MI: { avg_ppm: 306, classification: 'Very Hard' },
      MN: { avg_ppm: 270, classification: 'Very Hard' },
      MS: { avg_ppm: 53, classification: 'Soft' },
      MO: { avg_ppm: 270, classification: 'Very Hard' },
      MT: { avg_ppm: 211, classification: 'Very Hard' },
      NE: { avg_ppm: 253, classification: 'Very Hard' },
      NV: { avg_ppm: 273, classification: 'Very Hard' },
      NH: { avg_ppm: 19, classification: 'Soft' },
      NJ: { avg_ppm: 117, classification: 'Moderately Hard' },
      NM: { avg_ppm: 223, classification: 'Very Hard' },
      NY: { avg_ppm: 127, classification: 'Hard' },
      NC: { avg_ppm: 66, classification: 'Moderately Hard' },
      ND: { avg_ppm: 270, classification: 'Very Hard' },
      OH: { avg_ppm: 299, classification: 'Very Hard' },
      OK: { avg_ppm: 199, classification: 'Very Hard' },
      OR: { avg_ppm: 46, classification: 'Soft' },
      PA: { avg_ppm: 153, classification: 'Hard' },
      RI: { avg_ppm: 29, classification: 'Soft' },
      SC: { avg_ppm: 25, classification: 'Soft' },
      SD: { avg_ppm: 269, classification: 'Very Hard' },
      TN: { avg_ppm: 106, classification: 'Moderately Hard' },
      TX: { avg_ppm: 199, classification: 'Very Hard' },
      UT: { avg_ppm: 298, classification: 'Very Hard' },
      VT: { avg_ppm: 26, classification: 'Soft' },
      VA: { avg_ppm: 73, classification: 'Moderately Hard' },
      WA: { avg_ppm: 57, classification: 'Soft' },
      WV: { avg_ppm: 89, classification: 'Moderately Hard' },
      WI: { avg_ppm: 290, classification: 'Very Hard' },
      WY: { avg_ppm: 178, classification: 'Hard' },
    },

    // ── Representative city entries ────────────────────────────────────────
    // Extend this array by pasting additional entries from date.json.
    cities: [
      // West Coast / Pacific
      { city: 'Anchorage', state: 'AK', lat: 61.2880, lng: -149.4870, ppm: 63, gpg: 4, zips: ['99501', '99502', '99503', '99504', '99507', '99508', '99510'] },
      { city: 'Honolulu', state: 'HI', lat: 21.3069, lng: -157.8583, ppm: 90, gpg: 5, zips: ['96801', '96802', '96813', '96814', '96815', '96816', '96817'] },
      { city: 'Seattle', state: 'WA', lat: 47.6062, lng: -122.3321, ppm: 23, gpg: 1, zips: ['98101', '98102', '98103', '98104', '98105', '98115', '98121'] },
      { city: 'Portland', state: 'OR', lat: 45.5051, lng: -122.6750, ppm: 44, gpg: 3, zips: ['97201', '97202', '97203', '97204', '97205', '97206', '97209'] },
      { city: 'San Francisco', state: 'CA', lat: 37.7749, lng: -122.4194, ppm: 53, gpg: 3, zips: ['94102', '94103', '94104', '94105', '94107', '94110', '94111'] },
      { city: 'Los Angeles', state: 'CA', lat: 34.0522, lng: -118.2437, ppm: 312, gpg: 18, zips: ['90001', '90002', '90003', '90004', '90005', '90010', '90012'] },
      { city: 'San Diego', state: 'CA', lat: 32.7157, lng: -117.1611, ppm: 249, gpg: 15, zips: ['92101', '92102', '92103', '92104', '92105', '92108', '92115'] },
      { city: 'Oceanside', state: 'CA', lat: 33.1959, lng: -117.3795, ppm: 249, gpg: 15, zips: ['92054', '92056', '92057', '92058'] },
      { city: 'Las Vegas', state: 'NV', lat: 36.1699, lng: -115.1398, ppm: 309, gpg: 18, zips: ['89101', '89102', '89103', '89104', '89109', '89119', '89146'] },
      { city: 'Phoenix', state: 'AZ', lat: 33.4484, lng: -112.0740, ppm: 395, gpg: 23, zips: ['85001', '85002', '85003', '85004', '85006', '85012', '85013'] },
      { city: 'Tucson', state: 'AZ', lat: 32.2226, lng: -110.9747, ppm: 312, gpg: 18, zips: ['85701', '85702', '85703', '85704', '85705', '85711', '85716'] },
      // Mountain / Intermountain
      { city: 'Denver', state: 'CO', lat: 39.7392, lng: -104.9903, ppm: 127, gpg: 7, zips: ['80201', '80202', '80203', '80204', '80205', '80210', '80218'] },
      { city: 'Salt Lake City', state: 'UT', lat: 40.7608, lng: -111.8910, ppm: 298, gpg: 17, zips: ['84101', '84102', '84103', '84104', '84105', '84111', '84115'] },
      { city: 'Albuquerque', state: 'NM', lat: 35.0844, lng: -106.6504, ppm: 223, gpg: 13, zips: ['87101', '87102', '87103', '87104', '87105', '87110', '87111'] },
      { city: 'Boise', state: 'ID', lat: 43.6150, lng: -116.2023, ppm: 230, gpg: 13, zips: ['83701', '83702', '83703', '83704', '83705', '83709', '83712'] },
      { city: 'Billings', state: 'MT', lat: 45.7833, lng: -108.5007, ppm: 211, gpg: 12, zips: ['59101', '59102', '59105', '59106'] },
      // Texas / South-Central
      { city: 'Dallas', state: 'TX', lat: 32.7767, lng: -96.7970, ppm: 256, gpg: 15, zips: ['75201', '75202', '75203', '75204', '75205', '75206', '75209'] },
      { city: 'Houston', state: 'TX', lat: 29.7604, lng: -95.3698, ppm: 188, gpg: 11, zips: ['77001', '77002', '77003', '77004', '77005', '77006', '77008'] },
      { city: 'San Antonio', state: 'TX', lat: 29.4241, lng: -98.4936, ppm: 224, gpg: 13, zips: ['78201', '78202', '78203', '78204', '78205', '78207', '78209'] },
      { city: 'Oklahoma City', state: 'OK', lat: 35.4676, lng: -97.5164, ppm: 199, gpg: 12, zips: ['73101', '73102', '73103', '73104', '73105', '73107', '73111'] },
      // Midwest / Plains
      { city: 'Chicago', state: 'IL', lat: 41.8781, lng: -87.6298, ppm: 147, gpg: 9, zips: ['60601', '60602', '60603', '60604', '60605', '60606', '60610'] },
      { city: 'Minneapolis', state: 'MN', lat: 44.9778, lng: -93.2650, ppm: 270, gpg: 16, zips: ['55401', '55402', '55403', '55404', '55405', '55414', '55454'] },
      { city: 'Kansas City', state: 'MO', lat: 39.0997, lng: -94.5786, ppm: 270, gpg: 16, zips: ['64101', '64102', '64105', '64108', '64109', '64111', '64112'] },
      { city: 'Indianapolis', state: 'IN', lat: 39.7684, lng: -86.1581, ppm: 363, gpg: 21, zips: ['46201', '46202', '46203', '46204', '46205', '46208', '46219'] },
      { city: 'Columbus', state: 'OH', lat: 39.9612, lng: -82.9988, ppm: 299, gpg: 17, zips: ['43201', '43202', '43203', '43204', '43205', '43206', '43215'] },
      { city: 'Milwaukee', state: 'WI', lat: 43.0389, lng: -87.9065, ppm: 136, gpg: 8, zips: ['53201', '53202', '53203', '53204', '53205', '53207', '53209'] },
      { city: 'Omaha', state: 'NE', lat: 41.2565, lng: -95.9345, ppm: 253, gpg: 15, zips: ['68101', '68102', '68104', '68105', '68106', '68107', '68108'] },
      { city: 'Wichita', state: 'KS', lat: 37.6872, lng: -97.3301, ppm: 266, gpg: 16, zips: ['67201', '67202', '67203', '67204', '67205', '67206', '67207'] },
      // South / Southeast
      { city: 'Miami', state: 'FL', lat: 25.7617, lng: -80.1918, ppm: 216, gpg: 13, zips: ['33101', '33102', '33109', '33125', '33126', '33127', '33128'] },
      { city: 'Orlando', state: 'FL', lat: 28.5383, lng: -81.3792, ppm: 216, gpg: 13, zips: ['32801', '32802', '32803', '32804', '32805', '32806', '32808'] },
      { city: 'Atlanta', state: 'GA', lat: 33.7490, lng: -84.3880, ppm: 38, gpg: 2, zips: ['30301', '30303', '30305', '30306', '30307', '30309', '30310'] },
      { city: 'Nashville', state: 'TN', lat: 36.1627, lng: -86.7816, ppm: 106, gpg: 6, zips: ['37201', '37202', '37203', '37204', '37205', '37206', '37207'] },
      { city: 'Charlotte', state: 'NC', lat: 35.2271, lng: -80.8431, ppm: 66, gpg: 4, zips: ['28201', '28202', '28203', '28204', '28205', '28206', '28207'] },
      { city: 'New Orleans', state: 'LA', lat: 29.9511, lng: -90.0715, ppm: 97, gpg: 6, zips: ['70112', '70113', '70114', '70115', '70116', '70117', '70118'] },
      // Northeast
      { city: 'New York', state: 'NY', lat: 40.7128, lng: -74.0060, ppm: 44, gpg: 3, zips: ['10001', '10002', '10003', '10004', '10005', '10006', '10007'] },
      { city: 'Philadelphia', state: 'PA', lat: 39.9526, lng: -75.1652, ppm: 153, gpg: 9, zips: ['19101', '19102', '19103', '19104', '19106', '19107', '19109'] },
      { city: 'Boston', state: 'MA', lat: 42.3601, lng: -71.0589, ppm: 34, gpg: 2, zips: ['02101', '02102', '02103', '02108', '02109', '02110', '02111'] },
      { city: 'Washington', state: 'DC', lat: 38.9072, lng: -77.0369, ppm: 106, gpg: 6, zips: ['20001', '20002', '20003', '20004', '20005', '20006', '20007'] },
      { city: 'Baltimore', state: 'MD', lat: 39.2904, lng: -76.6122, ppm: 106, gpg: 6, zips: ['21201', '21202', '21203', '21204', '21205', '21206', '21210'] },
      { city: 'Pittsburgh', state: 'PA', lat: 40.4406, lng: -79.9959, ppm: 153, gpg: 9, zips: ['15201', '15202', '15203', '15204', '15205', '15206', '15210'] },
      // Louisville / Appalachian
      { city: 'Louisville', state: 'KY', lat: 38.2527, lng: -85.7585, ppm: 153, gpg: 9, zips: ['40201', '40202', '40203', '40204', '40205', '40206', '40207'] },
      { city: 'Charleston', state: 'WV', lat: 38.3498, lng: -81.6326, ppm: 62, gpg: 4, zips: ['25301', '25302', '25304', '25305', '25311', '25312', '25314'] },
    ],

    // ──────────────────────────────────────────────────────────────────────
    // getClassification(ppm) — MODIFIED FOR HAIR-CARE NICHE
    // Returns hair-specific impact language. "urgency" key maps to PRODUCTS.
    // ──────────────────────────────────────────────────────────────────────
    getClassification: function (ppm) {
      if (ppm <= 60) {
        return {
          level: 'Soft',
          color: '#4CAF50',
          bgColor: '#f0fdf4',
          borderColor: '#bbf7d0',
          urgency: 'low',
          description: 'Excellent for hair. Little to no mineral buildup on scalp.',
          hairImpact: 'Hair retains its natural moisture and protein structure. Shampoo lathers freely and rinses cleanly. Color treatments last longer, and scalp sebum levels stay balanced. Your water is unlikely to be a source of hair damage.',
          actionRequired: 'Standard hair care is sufficient. Maintain with a gentle daily shampoo and quality conditioner. A shower filter is optional but provides a useful buffer against trace chlorine from treatment.',
        };
      }
      if (ppm <= 120) {
        return {
          level: 'Moderately Hard',
          color: '#8BC34A',
          bgColor: '#f7fef0',
          borderColor: '#d9f99d',
          urgency: 'moderate',
          description: 'Minor mineral buildup. May cause slight hair dryness over time.',
          hairImpact: 'Gradual calcium and magnesium scale forms on hair shafts with repeated exposure, causing mild dullness, frizz, and reduced shine. Color-treated hair may fade 15–20% faster. Scalp buildup begins accumulating, potentially causing flakiness.',
          actionRequired: 'Introduce a chelating shampoo once per week to clear mineral deposits before they compound. A shower filter is recommended to reduce the mineral load at the source.',
        };
      }
      if (ppm <= 180) {
        return {
          level: 'Hard',
          color: '#FFC107',
          bgColor: '#fffbeb',
          borderColor: '#fde68a',
          urgency: 'high',
          description: 'Noticeable mineral buildup. Hair feels brittle and scalp is dry.',
          hairImpact: 'Calcium scale actively coats each strand, blocking moisture and making hair feel rough, straw-like, and prone to breakage. Conditioners cannot penetrate the mineral barrier. Scalp may become chronically flaky or itchy. Hair color fades 30–40% faster — highlights and toner wash out in days.',
          actionRequired: 'Use a chelating shampoo 2–3 times per week. A shower filter is strongly recommended. Consider a monthly scalp detox treatment to remove existing scale buildup.',
        };
      }
      return {
        level: 'Very Hard',
        color: '#F44336',
        bgColor: '#fff5f5',
        borderColor: '#fecaca',
        urgency: 'critical',
        description: 'Severe hard water. High risk of hair damage, color fading, and scalp calcification.',
        hairImpact: 'Extreme mineral concentration causes chronic dryness, brittleness, and breakage. Scalp calcification can partially block follicles, contributing to visible thinning over time. Color oxidises within days. Some users notice white mineral residue on darker hair after drying. This is the leading overlooked cause of unexplained hair damage in the US.',
        actionRequired: 'Use a chelating shampoo every single wash. Install a vitamin C or KDF shower filter — this is non-negotiable at this hardness level. Add a monthly deep scalp detox and weekly bond-repair treatment (e.g., Olaplex No. 3) to your routine.',
      };
    },

    // ── State brand color ──────────────────────────────────────────────────
    getStateColor: function (stateCode) {
      const s = this.stateAverages[stateCode];
      if (!s) return '#CCCCCC';
      return this.getClassification(s.avg_ppm).color;
    },

    // ── Nearest city by Euclidean lat/lng distance ─────────────────────────
    findNearestCity: function (lat, lng) {
      let nearest = null, minDist = Infinity;
      for (const c of this.cities) {
        const d = Math.sqrt(
          Math.pow(c.lat - lat, 2) + Math.pow(c.lng - lng, 2)
        );
        if (d < minDist) { minDist = d; nearest = c; }
      }
      return nearest;
    },

    // ── Filter cities by state ─────────────────────────────────────────────
    getCitiesByState: function (stateCode) {
      return this.cities.filter(c => c.state === stateCode);
    },

    // ── Full-text search across city, state, and ZIP ───────────────────────
    searchCities: function (query) {
      const q = query.toLowerCase().trim();
      return this.cities.filter(c =>
        c.city.toLowerCase().includes(q) ||
        c.state.toLowerCase().includes(q) ||
        (c.zips && c.zips.some(z => z.includes(q)))
      );
    },
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // ZIP-CODE → STATE LOOKUP  (3-digit prefix → USPS state code)
  // Used as the last-resort fallback when geocoding is unavailable.
  // ═══════════════════════════════════════════════════════════════════════════

  const ZIP3_TO_STATE = (function () {
    // [fromPrefix, toPrefix, stateCode]  — compact range format
    const ranges = [
      [10, 27, 'MA'], [28, 29, 'RI'], [30, 38, 'NH'], [39, 49, 'ME'],
      [50, 59, 'VT'], [60, 69, 'CT'], [70, 89, 'NJ'], [100, 149, 'NY'],
      [150, 196, 'PA'], [197, 199, 'DE'], [200, 205, 'DC'], [206, 219, 'MD'],
      [220, 246, 'VA'], [247, 268, 'WV'], [269, 289, 'NC'], [290, 299, 'SC'],
      [300, 319, 'GA'], [320, 349, 'FL'], [350, 369, 'AL'], [370, 385, 'TN'],
      [386, 397, 'MS'], [398, 399, 'GA'], [400, 427, 'KY'], [430, 458, 'OH'],
      [460, 479, 'IN'], [480, 499, 'MI'], [500, 528, 'IA'], [530, 549, 'WI'],
      [550, 567, 'MN'], [570, 577, 'SD'], [580, 588, 'ND'], [590, 599, 'MT'],
      [600, 629, 'IL'], [630, 658, 'MO'], [660, 679, 'KS'], [680, 693, 'NE'],
      [700, 714, 'LA'], [716, 729, 'AR'], [730, 749, 'OK'], [750, 799, 'TX'],
      [800, 816, 'CO'], [820, 831, 'WY'], [832, 838, 'ID'], [840, 847, 'UT'],
      [850, 865, 'AZ'], [870, 884, 'NM'], [889, 898, 'NV'], [900, 961, 'CA'],
      [967, 968, 'HI'], [970, 979, 'OR'], [980, 994, 'WA'], [995, 999, 'AK'],
    ];
    const map = {};
    for (const [from, to, st] of ranges) {
      for (let i = from; i <= to; i++) map[String(i).padStart(3, '0')] = st;
    }
    return map;
  })();

  function getStateFromZip(zip) {
    return ZIP3_TO_STATE[String(zip).substring(0, 3)] || null;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // LOCALSTORAGE CACHE  (7-day TTL, fails silently)
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Returns a valid cached result object, or null on miss / expiry / error.
   */
  function getCached(zip) {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + zip);
      if (!raw) return null;
      const entry = JSON.parse(raw);
      if (!entry?.timestamp || !entry?.data) return null;
      if (Date.now() - entry.timestamp > CACHE_EXPIRY_MS) {
        localStorage.removeItem(CACHE_PREFIX + zip);
        return null;
      }
      return entry.data;
    } catch (_) { return null; }
  }

  /**
   * Persists result to localStorage. Fails silently on quota / unavailability.
   */
  function setCached(zip, data) {
    try {
      localStorage.setItem(
        CACHE_PREFIX + zip,
        JSON.stringify({ timestamp: Date.now(), data })
      );
    } catch (_) { /* quota exceeded or private browsing mode — ignore */ }
  }

  /** Returns the cache age in human-readable form (e.g. "2h ago"). */
  function cacheAge(zip) {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + zip);
      if (!raw) return null;
      const { timestamp } = JSON.parse(raw);
      const ms = Date.now() - timestamp;
      if (ms < 3600000) return `${Math.round(ms / 60000)}m ago`;
      if (ms < 86400000) return `${Math.round(ms / 3600000)}h ago`;
      return `${Math.round(ms / 86400000)}d ago`;
    } catch (_) { return null; }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // API LAYER  (Steps 2–4)
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * STEP 2 — Nominatim geocoding: ZIP → { lat, lon }
   */
  async function fetchCoordinates(zip) {
    const url = `${API.NOMINATIM}?postalcode=${encodeURIComponent(zip)}&country=US&format=json&limit=1`;
    const res = await fetch(url, { headers: { 'Accept-Language': 'en-US,en' } });
    if (!res.ok) throw new Error(`Nominatim HTTP ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data) || !data.length) {
      throw new Error(`ZIP ${zip} not found by geocoder`);
    }
    return { lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) };
  }

  /**
     * STEP 3 — USGS site search: find nearby water quality station using Bounding Box (bBox)
     */
  async function fetchUSGSSite(lat, lon) {
    const offset = 0.22;
    const west = (lon - offset).toFixed(4);
    const south = (lat - offset).toFixed(4);
    const east = (lon + offset).toFixed(4);
    const north = (lat + offset).toFixed(4);

    // 💡 التغيير الأول: استخدام format=rdb لأن خدمة site لا تدعم json!
    // أضفنا أيضاً hasDataTypeCd=qw لضمان أن المحطة تقيس جودة المياه فعلياً
    const targetUrl = `${API.USGS_SITE}?format=rdb&bBox=${west},${south},${east},${north}&parameterCd=00900&hasDataTypeCd=qw`;

    const res = await fetch(PROXY_URL + encodeURIComponent(targetUrl));
    if (!res.ok) throw new Error(`USGS site search HTTP ${res.status}`);

    // قراءة البيانات كنص (Text) بدلاً من JSON
    const text = await res.text();

    // تحليل صيغة RDB (نص مفصول بمسافات جدولة - Tab-Separated)
    const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

    // البحث عن الترويسة (أول سطر لا يبدأ بعلامة #)
    let headerLineIndex = -1;
    for (let i = 0; i < lines.length; i++) {
      if (!lines[i].startsWith('#')) {
        headerLineIndex = i;
        break;
      }
    }

    // إذا لم نجد الترويسة، أو لم يكن هناك صفوف بيانات (البيانات تبدأ بعد الترويسة بصفين)
    if (headerLineIndex === -1 || headerLineIndex + 2 >= lines.length) {
      throw new Error('No USGS water quality stations found within this bounding box');
    }

    const headers = lines[headerLineIndex].split('\t');
    const siteNoIndex = headers.indexOf('site_no');
    const stationNmIndex = headers.indexOf('station_nm');

    if (siteNoIndex === -1) throw new Error('Invalid RDB format: missing site_no');

    // جلب أول محطة متوفرة في القائمة
    const firstDataRow = lines[headerLineIndex + 2].split('\t');
    const siteCode = firstDataRow[siteNoIndex];
    const siteName = stationNmIndex !== -1 ? firstDataRow[stationNmIndex] : 'USGS Station';

    if (siteCode) return { siteCode, siteName };

    throw new Error('No valid site code found in RDB response');
  }

  /**
   * STEP 4 — USGS daily values: read the most recent hardness measurement.
   */
  async function fetchUSGSData(siteCode) {
    // 💡 التغيير الثاني: استخدام format=json,1.1 لضمان التوافق التام مع سيرفرات البيانات
    const targetUrl = `${API.USGS_DV}?format=json,1.1&sites=${encodeURIComponent(siteCode)}&parameterCd=00900`;
    const res = await fetch(PROXY_URL + encodeURIComponent(targetUrl));

    if (!res.ok) throw new Error(`USGS DV HTTP ${res.status}`);
    const body = await res.json();

    const ts = body?.value?.timeSeries;
    if (!Array.isArray(ts) || ts.length === 0) {
      throw new Error(`No hardness time series returned for station ${siteCode}`);
    }

    const values = ts[0]?.values?.[0]?.value;
    if (!Array.isArray(values) || values.length === 0) {
      throw new Error(`Empty value array from USGS station ${siteCode}`);
    }

    // تنظيف البيانات من القيم المفقودة الخاصة بـ USGS مثل -999999
    const valid = values.filter(v => {
      const n = parseFloat(v?.value);
      return v?.value !== '' && v?.value !== '-999999' && v?.value !== 'NaN' && !isNaN(n);
    });
    if (!valid.length) throw new Error(`No valid hardness readings at station ${siteCode}`);

    // سحب أحدث قراءة
    const latest = valid[valid.length - 1];
    return {
      ppm: parseFloat(latest.value),
      dateTime: latest.dateTime || '',
      siteName: ts[0]?.sourceInfo?.siteName || 'USGS Station',
      siteCode,
    };
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // MAIN FUNCTION  — checkWaterHardness(zipCode)
  // ═══════════════════════════════════════════════════════════════════════════

  async function checkWaterHardness(zip) {

    // ── STEP 1: localStorage cache check ────────────────────────────────────
    const cached = getCached(zip);
    if (cached) {
      renderResults({ ...cached, fromCache: true, cacheAge: cacheAge(zip) });
      return;
    }

    renderLoading();
    let result = null;

    // ── STEPS 2–4: Live USGS API chain ───────────────────────────────────────
    try {
      // Step 2
      setLoadingStep(0);
      const { lat, lon } = await fetchCoordinates(zip);

      // Step 3
      setLoadingStep(1);
      const { siteCode, siteName } = await fetchUSGSSite(lat, lon);

      // Step 4
      setLoadingStep(2);
      const usgs = await fetchUSGSData(siteCode);

      const cls = waterHardnessData.getClassification(usgs.ppm);
      const state = getStateFromZip(zip);
      const stateAvg = state ? waterHardnessData.stateAverages[state] : null;

      result = {
        zip,
        ppm: usgs.ppm,
        gpg: +(usgs.ppm / 17.12).toFixed(1),
        classification: cls.level,
        color: cls.color,
        bgColor: cls.bgColor,
        borderColor: cls.borderColor,
        urgency: cls.urgency,
        description: cls.description,
        hairImpact: cls.hairImpact,
        actionRequired: cls.actionRequired,
        source: 'usgs-live',
        isLive: true,
        isEstimate: false,
        station: usgs.siteName,
        siteCode: usgs.siteCode,
        dataDate: usgs.dateTime,
        lat, lon, state,
        stateAvgPpm: stateAvg?.avg_ppm ?? null,
      };

    } catch (usgsErr) {
      // ── USGS chain failed — log and activate static fallback ─────────────
      console.warn('[WaterChecker] USGS chain failed:', usgsErr.message);
      console.info('[WaterChecker] Falling back to static database…');

      try {
        let lat = null, lon = null;

        // Re-attempt geocoding (Nominatim is more reliable than USGS)
        try {
          const c = await fetchCoordinates(zip);
          lat = c.lat; lon = c.lon;
        } catch (_) { /* geocoding also unavailable */ }

        let cityData = null;
        let fbSource = 'static-state-average';

        if (lat !== null && lon !== null) {
          cityData = waterHardnessData.findNearestCity(lat, lon);
          fbSource = 'static-nearest-city';
        }

        // Last resort: derive state from ZIP prefix → state average
        if (!cityData) {
          const st = getStateFromZip(zip);
          const avg = st ? waterHardnessData.stateAverages[st] : null;
          if (!avg) throw new Error('No fallback data found for this region');
          cityData = { city: `${st} (State Average)`, state: st, ppm: avg.avg_ppm };
        }

        const cls = waterHardnessData.getClassification(cityData.ppm);
        const stateAvg = waterHardnessData.stateAverages[cityData.state];

        result = {
          zip,
          ppm: cityData.ppm,
          gpg: +(cityData.ppm / 17.12).toFixed(1),
          classification: cls.level,
          color: cls.color,
          bgColor: cls.bgColor,
          borderColor: cls.borderColor,
          urgency: cls.urgency,
          description: cls.description,
          hairImpact: cls.hairImpact,
          actionRequired: cls.actionRequired,
          source: fbSource,
          isLive: false,
          isEstimate: true,
          nearestCity: cityData.city,
          state: cityData.state,
          lat, lon,
          stateAvgPpm: stateAvg?.avg_ppm ?? null,
        };

      } catch (fbErr) {
        renderError(
          `Unable to retrieve water hardness data for ZIP code <strong>${esc(zip)}</strong>.<br>
           Please check your internet connection and try again.`,
          usgsErr.message
        );
        return;
      }
    }

    // ── STEP 5: Cache + render ───────────────────────────────────────────────
    if (result) {
      setCached(zip, result);
      renderResults(result);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // RENDERING ENGINE
  // ═══════════════════════════════════════════════════════════════════════════

  const $ = sel => document.querySelector(sel);
  const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  function rc() { return $('#resultsContainer'); }
  function setHTML(h) { const el = rc(); if (el) el.innerHTML = h; }

  // ── Multi-step loading indicator ─────────────────────────────────────────

  function renderLoading() {
    setHTML(`
      <div class="whc-loading" role="status" aria-live="polite" aria-atomic="true">
        <div class="whc-spinner" aria-hidden="true">
          <div class="whc-spinner-ring"></div>
        </div>
        <p class="whc-loading-headline">Analyzing water quality…</p>
        <ol class="whc-steps" role="list" aria-label="Progress steps">
          ${LOAD_STEPS.map((s, i) => `
            <li class="whc-step" id="ls${i}" role="listitem">
              <span class="whc-step-ico" aria-hidden="true">${s.icon}</span>
              <span class="whc-step-txt">${esc(s.text)}</span>
              <span class="whc-step-dot pending" aria-label="Pending">●</span>
            </li>`).join('')}
        </ol>
      </div>`);
  }

  function setLoadingStep(i) {
    for (let j = 0; j < i; j++) {
      const el = $(`#ls${j}`);
      if (el) { el.classList.add('done'); const d = el.querySelector('.whc-step-dot'); if (d) { d.textContent = '✓'; d.className = 'whc-step-dot done'; } }
    }
    const cur = $(`#ls${i}`);
    if (cur) { cur.classList.add('active'); const d = cur.querySelector('.whc-step-dot'); if (d) { d.textContent = '◉'; d.className = 'whc-step-dot active'; } }
  }

  // ── Error state ───────────────────────────────────────────────────────────

  function renderError(msg, tech) {
    setHTML(`
      <div class="whc-error" role="alert" aria-live="assertive">
        <span class="whc-err-icon" aria-hidden="true">⚠️</span>
        <div class="whc-err-body">
          <p>${msg}</p>
          ${tech ? `<details class="whc-err-detail"><summary>Technical detail</summary><code>${esc(tech)}</code></details>` : ''}
        </div>
      </div>`);
  }

  // ── Main results card ─────────────────────────────────────────────────────

  function renderResults(data) {
    const {
      zip, ppm, gpg, classification, color, bgColor, borderColor,
      urgency, description, hairImpact, actionRequired,
      source, isLive, isEstimate, fromCache, cacheAge: age,
      station, siteCode, dataDate,
      nearestCity, state, stateAvgPpm,
    } = data;

    const prods = PRODUCTS[urgency] || PRODUCTS.low;
    const barPct = Math.min(100, Math.round((ppm / 450) * 100));

    // ── Source / cache badge ─────────────────────────────────────────────
    let badge = '';
    if (fromCache) {
      badge = `<span class="whc-badge whc-badge--cache">📦 Cached${age ? ' · ' + age : ''}</span>`;
    } else if (isLive) {
      badge = `<span class="whc-badge whc-badge--live">🟢 USGS Live Data</span>`;
    } else if (source === 'static-nearest-city') {
      badge = `<span class="whc-badge whc-badge--est">📍 Nearest City Estimate</span>`;
    } else {
      badge = `<span class="whc-badge whc-badge--est">🗺️ State Average Estimate</span>`;
    }

    // ── Estimate notice ──────────────────────────────────────────────────
    const estimateBar = isEstimate ? `
      <div class="whc-est-bar" role="note">
        <span aria-hidden="true">📍</span>
        <p>
          <strong>Estimated result for ZIP ${esc(zip)}.</strong>
          Live USGS data was unavailable for this area. Showing data for
          <strong>${esc(nearestCity || (state ? state + ' state average' : 'nearest region'))}</strong>
          — the closest entry in our regional database. Actual hardness may vary slightly.
        </p>
      </div>` : '';

    // ── USGS station credit ──────────────────────────────────────────────
    const stationRow = isLive && station ? `
      <div class="whc-station">
        <span aria-hidden="true">🔬</span>
        <div>
          <span class="whc-station-lbl">USGS Station</span>
          <span class="whc-station-val">${esc(station)}</span>
          <span class="whc-station-sub">Site #${esc(siteCode)}${dataDate ? ' · ' + esc(dataDate.substring(0, 10)) : ''}</span>
        </div>
      </div>` : '';

    // ── State average comparison ─────────────────────────────────────────
    const stateRow = stateAvgPpm && state ? (() => {
      const sc = waterHardnessData.getClassification(stateAvgPpm);
      return `<div class="whc-stat-item">
                <span class="whc-stat-lbl">${esc(state)} State Average</span>
                <span class="whc-stat-val" style="color:${sc.color}">${stateAvgPpm} ppm — ${esc(sc.level)}</span>
              </div>`;
    })() : '';

    // ── Hardness scale ticks ─────────────────────────────────────────────
    const TICKS = [
      { lbl: 'Soft', col: '#4CAF50', match: c => c === 'Soft' },
      { lbl: 'Mod. Hard', col: '#8BC34A', match: c => c === 'Moderately Hard' },
      { lbl: 'Hard', col: '#FFC107', match: c => c === 'Hard' },
      { lbl: 'Very Hard', col: '#F44336', match: c => c === 'Very Hard' },
    ];
    const scaleTicks = TICKS.map(t => {
      const on = t.match(classification);
      return `<span class="whc-tick${on ? ' whc-tick--on' : ''}" style="${on ? `color:${t.col};font-weight:800` : 'color:#aab'}">${on ? '▶ ' : ''}${t.lbl}</span>`;
    }).join('<span class="whc-tick-sep">›</span>');

    // ── Product cards ────────────────────────────────────────────────────
    const cards = prods.map(p => `
      <a href="${esc(p.url)}" target="_blank" rel="nofollow noopener sponsored"
         class="whc-prod" role="listitem"
         aria-label="View ${esc(p.name)} on Amazon (affiliate link)">
        <span class="whc-prod-ico" aria-hidden="true">${p.icon}</span>
        <div class="whc-prod-body">
          <span class="whc-prod-tag" style="background:${p.tagColor}1a;color:${p.tagColor};border-color:${p.tagColor}55">${esc(p.tag)}</span>
          <h4 class="whc-prod-name">${esc(p.name)}</h4>
          <p class="whc-prod-desc">${esc(p.desc)}</p>
        </div>
        <span class="whc-prod-cta" aria-hidden="true">View&nbsp;→</span>
      </a>`).join('');

    // ── Assemble the full results card ───────────────────────────────────
    setHTML(`
      <div class="whc-card"
           style="--wc:${color};--wb:${borderColor};--wbg:${bgColor};border-top:5px solid ${color};background:${bgColor}"
           role="region"
           aria-label="Water hardness report for ZIP code ${esc(zip)}">

        ${estimateBar}

        <!-- HEADER -->
        <div class="whc-head">
          <div class="whc-head-left">
            <p class="whc-eyebrow">Report for ZIP <strong>${esc(zip)}</strong></p>
            <h2 class="whc-city">${esc(nearestCity || (state ? state + ' Region' : zip))}</h2>
            <div class="whc-badge-row">${badge}</div>
          </div>
          <div class="whc-lvl-badge" style="background:${color}" role="img"
               aria-label="Hardness: ${esc(classification)}">${esc(classification)}</div>
        </div>

        <!-- PPM -->
        <div class="whc-ppm-block">
          <div class="whc-ppm-row">
            <span class="whc-ppm-num" style="color:${color}">${ppm}</span>
            <div class="whc-ppm-meta">
              <span class="whc-ppm-unit">mg/L (ppm)</span>
              <span class="whc-ppm-gpg">${gpg}&nbsp;grains&nbsp;per&nbsp;gallon</span>
            </div>
          </div>
          <div class="whc-bar-wrap"
               role="progressbar" aria-valuenow="${ppm}"
               aria-valuemin="0" aria-valuemax="450"
               aria-label="${ppm} parts per million">
            <div class="whc-bar-track">
              <div class="whc-bar-zones" aria-hidden="true">
                <div style="width:13.3%;background:#4CAF5018"></div>
                <div style="width:13.3%;background:#8BC34A18"></div>
                <div style="width:13.3%;background:#FFC10718"></div>
                <div style="flex:1;background:#F4433618"></div>
              </div>
              <div class="whc-bar-fill" style="width:${barPct}%;background:${color}"></div>
            </div>
            <div class="whc-bar-axis" aria-hidden="true">
              <span>0</span><span>60</span><span>120</span><span>180</span><span>450+ ppm</span>
            </div>
          </div>
          <div class="whc-ticks" aria-hidden="true">${scaleTicks}</div>
        </div>

        <!-- STATS -->
        <div class="whc-stats">
          <div class="whc-stat-item">
            <span class="whc-stat-lbl">Classification</span>
            <span class="whc-stat-val" style="color:${color};font-weight:700">${esc(classification)}</span>
          </div>
          <div class="whc-stat-item">
            <span class="whc-stat-lbl">Hardness (mg/L)</span>
            <span class="whc-stat-val">${ppm} mg/L as CaCO₃</span>
          </div>
          <div class="whc-stat-item">
            <span class="whc-stat-lbl">Hardness (gpg)</span>
            <span class="whc-stat-val">${gpg} grains / gallon</span>
          </div>
          ${stateRow}
        </div>

        ${stationRow}

        <!-- HAIR IMPACT -->
        <div class="whc-impact">
          <h3 class="whc-section-title"><span aria-hidden="true">🪮</span> What This Means for Your Hair</h3>
          <p class="whc-impact-summary">${esc(description)}</p>
          <div class="whc-impact-list">
            <div class="whc-impact-item">
              <span class="whc-impact-ico" aria-hidden="true">⚡</span>
              <div>
                <strong class="whc-impact-lbl">Hair &amp; Scalp Effects</strong>
                <p>${esc(hairImpact)}</p>
              </div>
            </div>
            <div class="whc-impact-item">
              <span class="whc-impact-ico" aria-hidden="true">✅</span>
              <div>
                <strong class="whc-impact-lbl">Recommended Action</strong>
                <p>${esc(actionRequired)}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- PRODUCTS -->
        <div class="whc-prods">
          <h3 class="whc-section-title"><span aria-hidden="true">🛒</span> Recommended for ${esc(ppm + ' ppm')} Water</h3>
          <p class="whc-prods-intro">Selected specifically for your water hardness profile to protect and restore hair health:</p>
          <div class="whc-prod-list" role="list">${cards}</div>
          <p class="whc-affil-note">★ Amazon affiliate links — we earn a small commission at no extra cost to you.</p>
        </div>

        <!-- CTA -->
        <div class="whc-cta">
          <p>Understand the science behind why hard water damages hair:</p>
          <div class="whc-cta-links">
            <a href="/blog/hard-water-hair-damage/" class="whc-cta-btn">How Hard Water Damages Hair →</a>
            <a href="/blog/shampoos-that-work-hard-water-hair/" class="whc-cta-btn whc-cta-btn--sec">Best Chelating Shampoos →</a>
          </div>
        </div>

      </div>`);

    // Smooth-scroll to results
    const el = rc();
    if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // INPUT, VALIDATION, AND BUTTON STATE
  // ═══════════════════════════════════════════════════════════════════════════

  function showInputError(msg) {
    const inp = $('#zipInput');
    const hint = $('#zipHint');
    if (inp) { inp.classList.add('whc-inp-err'); setTimeout(() => inp.classList.remove('whc-inp-err'), 2400); }
    if (hint) {
      hint.textContent = msg;
      hint.style.color = '#dc2626';
      hint.setAttribute('role', 'alert');
      setTimeout(() => { hint.textContent = 'US ZIP codes only · Your data is never stored on our servers'; hint.style.color = ''; hint.removeAttribute('role'); }, 3500);
    }
  }

  function setBtnState(state, label) {
    const btn = $('#checkBtn');
    if (!btn) return;
    btn.disabled = state === 'checking';
    btn.innerHTML = state === 'checking'
      ? `<span class="whc-btn-spin" aria-hidden="true"></span>${esc(label)}`
      : esc(label);
    btn.dataset.state = state;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // INITIALISATION
  // ═══════════════════════════════════════════════════════════════════════════

  function init() {
    const btn = $('#checkBtn');
    const inp = $('#zipInput');
    if (!btn || !inp) {
      console.error('[WaterChecker] Could not find #checkBtn or #zipInput');
      return;
    }

    setBtnState('ready', 'Check My Water →');

    // Digits-only enforcement
    inp.addEventListener('input', () => {
      inp.value = inp.value.replace(/\D/g, '').substring(0, 5);
      const el = rc();
      if (el && el.dataset.lastZip && inp.value !== el.dataset.lastZip) {
        el.innerHTML = ''; delete el.dataset.lastZip;
      }
    });

    async function onSubmit() {
      const zip = inp.value.trim();
      if (!/^\d{5}$/.test(zip)) {
        showInputError('Please enter a valid 5-digit US ZIP code — e.g. 92054.');
        inp.focus(); return;
      }
      setBtnState('checking', 'Checking…');
      const el = rc(); if (el) el.dataset.lastZip = zip;
      try { await checkWaterHardness(zip); }
      finally { setBtnState('ready', 'Check My Water →'); }
    }

    btn.addEventListener('click', onSubmit);
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') onSubmit(); });
  }

  // Bootstrap
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})(); // end IIFE