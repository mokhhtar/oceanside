# Oceanside Hair Salon — Jekyll Project

A production-ready Jekyll SSG project for [oceansidehairsalon.com](https://oceansidehairsalon.com). Fully modular, DRY architecture with structured data extraction, SCSS compilation, and dynamic Schema.org JSON-LD generation.

---

## Quick Start

### Prerequisites
- Ruby ≥ 3.1
- Bundler (`gem install bundler`)

### Install & Run

```bash
# 1. Clone / unzip the project
cd oceanside-jekyll

# 2. Install gems
bundle install

# 3. Serve locally (auto-reload)
bundle exec jekyll serve --livereload

# 4. Visit http://localhost:4000
```

### Build for Production

```bash
JEKYLL_ENV=production bundle exec jekyll build
# Output → _site/
```

---

## Project Structure

```
.
├── _config.yml                   # Global settings, brand tokens, GA IDs
├── Gemfile                       # Ruby gem dependencies
├── robots.txt                    # Crawler directives
├── index.html                    # Homepage
├── 404.html                      # Custom 404 page
│
├── _data/                        # ── All hardcoded data lives here ──
│   ├── navigation.yml            # Navbar items & dropdowns
│   ├── footer.yml                # Footer columns, links, social SVGs
│   ├── products.yml              # 7 chelating shampoos (affiliate data)
│   └── faqs.yml                  # FAQ questions & answers (keyed by post)
│
├── _includes/                    # ── Reusable Liquid components ──
│   ├── head.html                 # <head> with dynamic Schema JSON-LD
│   ├── header.html               # Navbar (from navigation.yml)
│   ├── footer.html               # Footer (from footer.yml)
│   ├── product-card.html         # Amazon product card template
│   ├── faq-accordion.html        # Accessible FAQ accordion
│   ├── alert-box.html            # Highlight / info boxes
│   └── image-figure.html         # <figure> + <figcaption> wrapper
│
├── _layouts/
│   ├── default.html              # Base HTML shell
│   └── post.html                 # Blog post layout (hero + content-container)
│
├── _posts/
│   └── 2026-03-01-shampoos-that-work-hard-water-hair.md
│
└── assets/
    ├── css/
    │   └── main.scss             # Full SCSS (SASS vars → CSS custom props)
    └── js/
        └── main.js               # FAQ toggle, mobile nav, smooth scroll
```

---

## Adding a New Blog Post

1. Create `_posts/YYYY-MM-DD-your-slug.md`
2. Set front matter (copy from the existing post as a template):

```yaml
---
layout: post
title: "Your Post Title"
description: "SEO meta description."
date: 2026-03-01
hero_image: "/images/blog/your-folder/header.jpg"
hero_title: "Displayed H1 Title"
hero_subtitle: "Subtitle under H1"
faq_key: "your_faq_key"           # key in _data/faqs.yml
product_list_key: "products"      # key in _data/*.yml
breadcrumbs:
  - name: "Home"
    url: "/"
  - name: "Blog"
    url: "/blog/"
  - name: "Your Post Title"
    url: "/blog/your-slug/"
---
```

3. Write your content in Markdown. Inject includes:

```liquid
{% include product-card.html product=product %}
{% include faq-accordion.html faq_key="your_faq_key" %}
{% include alert-box.html content=alert_content %}
```

---

## Adding New Products

Edit `_data/products.yml`. Add a new entry following the existing schema — the product card and ItemList Schema are both generated automatically.

## Adding New FAQs

Edit `_data/faqs.yml`. Add a new named key (e.g. `electric_shavers`) and list Q&A pairs. Reference it in your post's front matter with `faq_key: electric_shavers`.

---

## Deployment

### GitHub Pages (with Actions)

Push to `main`. Add `.github/workflows/jekyll.yml`:

```yaml
name: Build and Deploy
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-ruby@v1
        with:
          ruby-version: '3.2'
      - run: bundle install
      - run: JEKYLL_ENV=production bundle exec jekyll build
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./_site
```

### Netlify / Cloudflare Pages

Build command: `bundle exec jekyll build`  
Publish directory: `_site`  
Environment variable: `JEKYLL_ENV=production`

---

## Amazon Affiliate Compliance

- The affiliate disclaimer is stored in `_config.yml` under `amazon.disclaimer` and injected once per product list page via the Markdown file.
- All product `amazon_url` values include `tag=oceansidehair-20`.
- `rel="nofollow noopener"` is set on all Amazon links inside `product-card.html`.
