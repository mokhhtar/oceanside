/**
 * assets/js/main.js
 * Oceanside Hair Salon — Site-wide JavaScript
 *
 * Responsibilities:
 *  1. FAQ accordion toggle (accessible, aria-driven)
 *  2. Mobile navbar: tap to open dropdowns
 *  3. Smooth scroll for anchor links
 *  4. Active nav link highlighting
 */

(function () {
  'use strict';

  // ─────────────────────────────────────────────
  // 1. FAQ ACCORDION
  // ─────────────────────────────────────────────
  /**
   * Works with _includes/faq-accordion.html.
   * Each .faq-item contains a .faq-question button and a .faq-answer div.
   * Toggling one item collapses all others (accordion behaviour).
   */
  function initFaqAccordion() {
    var faqButtons = document.querySelectorAll('.faq-question');
    if (!faqButtons.length) return;

    faqButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var item       = btn.parentElement;
        var isActive   = item.classList.contains('active');
        var allItems   = document.querySelectorAll('.faq-item');

        // Collapse all
        allItems.forEach(function (el) {
          el.classList.remove('active');
          el.querySelector('.faq-question').setAttribute('aria-expanded', 'false');
        });

        // Expand clicked item (unless it was already open)
        if (!isActive) {
          item.classList.add('active');
          btn.setAttribute('aria-expanded', 'true');
        }
      });

      // Keyboard: allow Space / Enter to toggle (buttons already handle Enter natively)
      btn.addEventListener('keydown', function (e) {
        if (e.key === ' ') {
          e.preventDefault();
          btn.click();
        }
      });
    });
  }

  // ─────────────────────────────────────────────
  // 2. MOBILE NAVBAR — tap to open dropdowns
  // ─────────────────────────────────────────────
  /**
   * On touch / small screens the CSS :hover trick doesn't work reliably.
   * This adds a click listener to each .dropbtn so tapping opens the
   * dropdown, and tapping anywhere else closes it.
   */
  function initMobileNav() {
    var dropbtns = document.querySelectorAll('.dropbtn');
    if (!dropbtns.length) return;

    dropbtns.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var dropdown = btn.nextElementSibling; // .dropdown-content
        if (!dropdown) return;

        var isOpen = dropdown.classList.contains('open');

        // Close all other open dropdowns
        document.querySelectorAll('.dropdown-content.open').forEach(function (el) {
          el.classList.remove('open');
          el.previousElementSibling.setAttribute('aria-expanded', 'false');
        });

        // Toggle this one
        if (!isOpen) {
          dropdown.classList.add('open');
          btn.setAttribute('aria-expanded', 'true');
        }
      });
    });

    // Close dropdowns when clicking outside the navbar
    document.addEventListener('click', function () {
      document.querySelectorAll('.dropdown-content.open').forEach(function (el) {
        el.classList.remove('open');
        el.previousElementSibling.setAttribute('aria-expanded', 'false');
      });
    });
  }

  /**
   * Inject a tiny CSS rule so .dropdown-content.open { display: block }
   * works alongside the existing CSS :hover rule — no SCSS change required.
   */
  function injectMobileNavStyle() {
    var style = document.createElement('style');
    style.textContent = '.dropdown-content.open { display: block; }';
    document.head.appendChild(style);
  }

  // ─────────────────────────────────────────────
  // 3. SMOOTH SCROLL for anchor links
  // ─────────────────────────────────────────────
  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
      anchor.addEventListener('click', function (e) {
        var target = document.querySelector(anchor.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        // Offset for fixed navbar (~60px)
        var navbarHeight = document.querySelector('.navbar')
          ? document.querySelector('.navbar').offsetHeight
          : 70;
        var top = target.getBoundingClientRect().top + window.pageYOffset - navbarHeight - 16;
        window.scrollTo({ top: top, behavior: 'smooth' });
      });
    });
  }

  // ─────────────────────────────────────────────
  // 4. ACTIVE NAV LINK
  // ─────────────────────────────────────────────
  function initActiveNav() {
    var currentPath = window.location.pathname;
    document.querySelectorAll('.navbar a').forEach(function (link) {
      if (link.getAttribute('href') === currentPath) {
        link.setAttribute('aria-current', 'page');
        link.style.color = 'var(--accent-color)';
      }
    });
  }

  // ─────────────────────────────────────────────
  // INIT — run after DOM is ready
  // ─────────────────────────────────────────────
  function init() {
    initFaqAccordion();
    injectMobileNavStyle();
    initMobileNav();
    initSmoothScroll();
    initActiveNav();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
