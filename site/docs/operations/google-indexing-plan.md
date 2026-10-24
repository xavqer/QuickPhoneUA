# Google Indexing Plan

Created: 2026-03-10

Use this plan to get the production QuickPhoneUA site into Google's organic search results and then measure what is actually indexed.

## Goal

- Make the public storefront discoverable and indexable in Google Search.
- Prioritize indexing for the home page, catalog, and active product detail pages.
- Keep transactional and account pages out of search results.

## Step 1. Technical SEO Foundation

Implement and deploy:

- `sitemap.xml` with the home page, catalog, privacy policy, and active product pages.
- `robots.txt` with a `Sitemap:` directive.
- Canonical URLs in the shared base template.
- Meta descriptions for the main indexable pages.
- `noindex,nofollow` for checkout, login, registration, profile, password reset, and phone change pages.
- `noindex,follow` for filtered catalog results and unavailable product detail pages.

Production note:

- The production default is now set to `https://quickphone.com.ua`.
- If you ever move the site, override `SITE_BASE_URL` in the production environment.

## Step 2. Google Search Console

- Add the production domain as a `Domain property` in Google Search Console.
- Verify ownership through a DNS TXT record.
- Wait until Google confirms ownership before moving on.

## Step 3. Sitemap Submission

- Open the `Sitemaps` section in Search Console.
- Submit `https://quickphone.com.ua/sitemap.xml`.
- Confirm that Google can fetch it without errors.

## Step 4. Request Initial Indexing

Use the URL Inspection tool to request indexing for:

- the home page
- the catalog page
- the privacy policy page
- 5 to 10 important in-stock product pages

## Step 5. Content and Internal Linking Review

Check that indexable pages have:

- a unique title
- a meaningful meta description
- visible text content, not only images
- clear internal links from home and catalog to product pages

## Step 6. Measurement Loop

After deploy and Search Console submission:

- review the `Page indexing` report
- review the `Performance` report
- watch for `Crawled - currently not indexed`, `Duplicate`, and `Blocked` states
- re-check results after 7 to 14 days

## Current Status

As of 2026-03-10, Step 1 is implemented in code and requires production deploy plus Search Console setup.
