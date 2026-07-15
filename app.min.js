(function () {
  const stack = document.querySelector('#menu-stack');
  const board = document.querySelector('.menu-board');
  const boardTitle = document.querySelector('#menu-board-title');
  const nav = document.querySelector('#category-nav');
  const navWrap = document.querySelector('.category-nav-wrap');
  const ambientStage = document.querySelector('.ambient-stage');
  const titleLinks = document.querySelector('#title-links');
  const footerUrl = document.querySelector('#footer-url');
  const brandLogo = document.querySelector('.brand-logo');
  const fallbackData = document.querySelector('#menu-data-fallback');
  const dialog = document.querySelector('#product-dialog');
  const dialogMedia = document.querySelector('#dialog-media');
  const dialogClose = document.querySelector('#dialog-close');
  const dialogMeta = document.querySelector('#dialog-meta');
  const dialogTitle = document.querySelector('#dialog-title');
  const dialogDescription = document.querySelector('#dialog-description');
  const dialogLabel = document.querySelector('#dialog-label');
  const dialogComposition = document.querySelector('#dialog-composition');
  const dialogPrice = document.querySelector('#dialog-price');

  let menuData = null;
  let menuSections = [];
  let sectionById = new Map();
  let chipMap = new Map();
  let categoryMarker = null;
  let activeProducts = [];
  let markerTimer = 0;
  let renderTimer = 0;
  let stackHeightTimer = 0;
  let scrollTicking = false;
  const preloadedImages = new Set();
  const ASSET_VERSION = '0d6090211c';

  const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const versionedAsset = (value = '') => {
    const url = String(value);
    if (!url || url.startsWith('#') || url.startsWith('data:') || /^(?:https?:)?\/\//i.test(url)) return url;

    const hashIndex = url.indexOf('#');
    const base = hashIndex >= 0 ? url.slice(0, hashIndex) : url;
    const hash = hashIndex >= 0 ? url.slice(hashIndex) : '';
    if (/[?&]version=/.test(base)) return url;

    return `${base}${base.includes('?') ? '&' : '?'}version=${encodeURIComponent(ASSET_VERSION)}${hash}`;
  };

  const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }[char]));

  const cleanTitle = (value = '') => String(value).replace(/\s+/g, ' ').trim();
  const productTitle = (product) => cleanTitle(product.name);

  const loadMenuData = async () => {
    const readFallback = () => JSON.parse(fallbackData?.textContent || '{}');
    return readFallback();
  };

  const productIcon = (type) => {
    const icons = {
      beer: '<path d="M18 14h16v24a7 7 0 0 1-7 7h-2a7 7 0 0 1-7-7V14Z"/><path d="M34 20h5a6 6 0 0 1 0 12h-5"/><path d="M21 14c-1.4-3.7.7-7 4.6-5.4 1.4-3.8 7.4-2.6 7 2.2 4.1-.4 5.8 2.8 3.2 5.2"/><path d="M24 20v17"/><path d="M29 20v17"/>',
      bottle: '<path d="M25 6h8"/><path d="M27 6v11l-4 6v19a5 5 0 0 0 5 5h2a5 5 0 0 0 5-5V23l-4-6V6"/><path d="M23 29h12"/><path d="M23 38h12"/>',
      soft: '<path d="M19 15h20"/><path d="m23 15 3 31h6l3-31"/><path d="M28 15 36 5"/><path d="M24 28h10"/><path d="M25 35h8"/>',
      cocktail: '<path d="M14 10h28L29 27v16"/><path d="M21 46h16"/><path d="M20 16h16"/><path d="M35 10l7-6"/><circle cx="43" cy="4" r="2"/>',
      shot: '<path d="M18 13h20l-4 31H22L18 13Z"/><path d="M21 24h14"/><path d="M23 35h10"/>',
      wine: '<path d="M20 8h18l-3 18a8 8 0 0 1-12 0L20 8Z"/><path d="M23 18h12"/><path d="M29 34v11"/><path d="M22 46h14"/>',
      coffee: '<path d="M16 17h22v15a8 8 0 0 1-8 8h-6a8 8 0 0 1-8-8V17Z"/><path d="M38 22h3a5 5 0 0 1 0 10h-3"/><path d="M21 9v4"/><path d="M28 7v5"/><path d="M35 9v4"/><path d="M18 44h20"/>',
      tea: '<path d="M15 20h22v14a8 8 0 0 1-8 8h-6a8 8 0 0 1-8-8V20Z"/><path d="M37 24h4a5 5 0 0 1 0 10h-4"/><path d="M20 11c2 1.5 2 3 0 4.5"/><path d="M27 9c2 1.5 2 3 0 4.5"/><path d="M34 11c2 1.5 2 3 0 4.5"/>',
      lemonade: '<path d="M18 14h20l-3 31H21L18 14Z"/><path d="M22 25h12"/><path d="M26 14 35 5"/><circle cx="38" cy="7" r="4"/><path d="M24 34h10"/>',
      soup: '<path d="M14 25h28a12 12 0 0 1-12 13h-4a12 12 0 0 1-12-13Z"/><path d="M17 42h22"/><path d="M21 14c2 1.5 2 3 0 4.5"/><path d="M28 12c2 1.5 2 3 0 4.5"/><path d="M35 14c2 1.5 2 3 0 4.5"/>',
      salad: '<path d="M14 25h28l-4 14H18l-4-14Z"/><path d="M21 25c0-7 9-9 12-3"/><path d="M29 25c1-6 9-7 11-1"/><path d="M18 18c4-2 8-1 10 3"/>',
      sauce: '<path d="M24 7h9"/><path d="M26 7v9l-5 7v18a5 5 0 0 0 5 5h5a5 5 0 0 0 5-5V23l-5-7V7"/><path d="M21 30h15"/><path d="M25 38h7"/>',
      wrap: '<path d="M17 14h24L30 46H20L17 14Z"/><path d="M21 20h16"/><path d="M22 28h12"/><path d="M24 36h8"/><path d="M25 14c1-5 8-5 9 0"/>',
      food: '<path d="M16 26h26"/><path d="M19 26a11 11 0 0 1 22 0"/><path d="M14 36h30"/><path d="M21 42h16"/><path d="M30 12v5"/>',
      drink: '<path d="M19 12h20l-3 34H22L19 12Z"/><path d="M23 24h12"/><path d="M27 12 35 5"/>'
    };
    const iconMarkup = (icons[type] || icons.drink).replace(/<(path|circle)\b/g, '<$1 pathLength="1"');
    return `<svg class="media-icon" viewBox="0 0 56 56" aria-hidden="true">${iconMarkup}</svg>`;
  };

  const linkIcon = (link) => {
    const icons = {
      instagram: '<rect x="10" y="10" width="36" height="36" rx="11"/><circle cx="28" cy="28" r="9"/><circle cx="39" cy="17" r="2.5"/>',
      'google-maps': '<path d="M28 6c8 0 14 6 14 14 0 10-14 26-14 26S14 30 14 20C14 12 20 6 28 6Z"/><circle cx="28" cy="20" r="5"/><path d="M18 43h20"/>',
      'yandex-maps': '<path d="M28 6c8 0 14 6 14 14 0 10-14 26-14 26S14 30 14 20C14 12 20 6 28 6Z"/><circle cx="28" cy="20" r="5"/><path d="M24 14h8M28 25v11"/>',
      external: '<path d="M18 15h23v23H18z"/><path d="M28 15h13v13"/><path d="M41 15 25 31"/>'
    };
    const iconMarkup = icons[link.icon || link.id] || icons.external;
    return `<svg class="title-link-icon" viewBox="0 0 56 56" aria-hidden="true">${iconMarkup}</svg>`;
  };

  const renderBrand = () => {
    if (!menuData?.brand) return;

    if (brandLogo && menuData.brand.logo) {
      const logoSrc = versionedAsset(menuData.brand.logo);
      brandLogo.src = logoSrc;
      brandLogo.alt = `${menuData.brand.name || 'Iliamo'} ${menuData.brand.subtitle || ''}`.trim();
      document.documentElement.style.setProperty('--logo-watermark', `url("${logoSrc}")`);
    }

    if (footerUrl && menuData.brand.siteUrl) {
      footerUrl.textContent = menuData.brand.siteUrl;
    }

    const links = menuData.brand.links || [];
    const shortLabel = (link) => ({
      instagram: 'Insta',
      'google-maps': 'Google',
      'yandex-maps': 'Yandex'
    }[link.icon || link.id] || link.label);

    if (titleLinks) {
      titleLinks.innerHTML = links.map((link) => `
        <li>
          <a href="${escapeHtml(link.url)}" target="_blank" rel="noopener noreferrer" data-link="${escapeHtml(link.icon || link.id)}" aria-label="${escapeHtml(link.label)}">
            ${linkIcon(link)}
            <span class="title-link-label">${escapeHtml(link.label)}</span>
            <span class="title-link-short" aria-hidden="true">${escapeHtml(shortLabel(link))}</span>
          </a>
        </li>
      `).join('');
    }
  };

  const renderNav = () => {
    const categories = menuData.categories?.length
      ? menuData.categories
      : menuSections.map(({ id, title, theme }) => ({ id, title, label: title, theme, icon: id }));
    const mobileCategoryLabel = (category) => category.label || category.title;

    nav.innerHTML = '<span class="category-marker" aria-hidden="true"></span>' + categories.map((category) => `
      <a href="#${escapeHtml(category.id)}" class="category-chip" data-category="${escapeHtml(category.id)}" data-theme="${escapeHtml(category.theme)}" aria-label="${escapeHtml(category.label || category.title)}" title="${escapeHtml(category.label || category.title)}">
        <span class="chip-label chip-label-full">${escapeHtml(category.label || category.title)}</span>
        <span class="chip-label chip-label-short" aria-hidden="true">${escapeHtml(mobileCategoryLabel(category))}</span>
      </a>
    `).join('');

    categoryMarker = nav.querySelector('.category-marker');
    chipMap = new Map([...nav.querySelectorAll('.category-chip[data-category]')].map((chip) => [chip.dataset.category, chip]));
    nav.querySelectorAll('.category-chip[data-category]').forEach((chip) => {
      chip.addEventListener('click', (event) => {
        event.preventDefault();
        renderSection(chip.dataset.category, { scroll: true });
      });
    });
  };

  const sectionPriceFromNote = (section) => {
    if (section.id === 'tea') return '11 ₾';
    if (section.id === 'sauces') return '3 ₾';
    const match = String(section.note || '').match(/\d+\s*₾/);
    return match ? match[0].replace(/\s+/g, ' ') : '';
  };

  const sectionDisplayNote = (section) => {
    if (section.id === 'strong' || section.id === 'wine') return section.note || '';
    return '';
  };

  const keepChipVisible = (chip) => {
    if (!chip) return;
    const maxLeft = Math.max(0, nav.scrollWidth - nav.clientWidth);
    const targetLeft = chip.offsetLeft - nav.clientWidth / 2 + chip.offsetWidth / 2;
    nav.scrollTo({
      left: Math.min(Math.max(0, targetLeft), maxLeft),
      behavior: reducedMotion() ? 'auto' : 'smooth'
    });
  };

  const syncCategoryMarker = (chip = document.querySelector('.category-chip.is-active')) => {
    if (!chip || !categoryMarker) return;
    if (!reducedMotion()) {
      nav.classList.add('is-marker-moving');
      window.clearTimeout(markerTimer);
      markerTimer = window.setTimeout(() => nav.classList.remove('is-marker-moving'), 440);
    }
    nav.style.setProperty('--marker-x', `${chip.offsetLeft}px`);
    nav.style.setProperty('--marker-y', `${chip.offsetTop}px`);
    nav.style.setProperty('--marker-w', `${chip.offsetWidth}px`);
    nav.style.setProperty('--marker-h', `${chip.offsetHeight}px`);
    nav.style.setProperty('--marker-color', chip.dataset.theme === 'food' ? 'var(--brown)' : 'var(--navy)');
    nav.style.setProperty('--marker-opacity', '1');
  };

  const setActive = (id) => {
    chipMap.forEach((chip) => {
      chip.classList.remove('is-active');
      chip.removeAttribute('aria-current');
    });

    const active = chipMap.get(id);
    if (!active) return;
    active.classList.add('is-active');
    active.setAttribute('aria-current', 'true');
    requestAnimationFrame(() => syncCategoryMarker(active));
    keepChipVisible(active);
  };

  const boardTop = () => board.getBoundingClientRect().top + window.scrollY;

  const targetScrollForActiveSection = () => {
    const navHeight = document.querySelector('.category-nav-wrap')?.getBoundingClientRect().height || 0;
    const desiredTarget = Math.max(0, boardTop() - navHeight - 12);
    const heldHeight = parseFloat(stack.style.minHeight) || 0;
    const activeHeight = Math.ceil(stack.querySelector('.active-section-body')?.getBoundingClientRect().height || 0);
    const artificialHeight = Math.max(0, heldHeight - activeHeight);
    const finalScrollHeight = Math.max(window.innerHeight, document.documentElement.scrollHeight - artificialHeight);
    const maxFinalScroll = Math.max(0, finalScrollHeight - window.innerHeight);
    return Math.min(desiredTarget, maxFinalScroll);
  };

  const scrollToBoardStart = (behavior = 'smooth') => {
    window.scrollTo({
      top: targetScrollForActiveSection(),
      behavior: reducedMotion() ? 'auto' : behavior
    });
  };

  const syncWatermarkMotion = () => {
    if (!ambientStage) return;

    const navBottom = Math.max(0, navWrap?.getBoundingClientRect().bottom || 0);
    const isMobile = window.innerWidth <= 640;
    const offset = isMobile ? 220 : window.innerWidth <= 1024 ? 230 : 260;
    ambientStage.style.setProperty('--watermark-top', `${Math.round(navBottom + offset)}px`);

    if (reducedMotion()) {
      ambientStage.style.setProperty('--watermark-y', '0px');
      ambientStage.style.setProperty('--watermark-rotate', '0deg');
      ambientStage.style.setProperty('--watermark-scale', '1');
      ambientStage.style.setProperty('--watermark-opacity', '0.056');
      return;
    }

    const scroll = window.scrollY || 0;
    const parallaxY = Math.max(-128, Math.min(64, Math.round(-scroll * 0.22 + Math.sin(scroll / 140) * 20)));
    const rotate = Math.max(-2.2, Math.min(2.2, Math.sin(scroll / 260) * 2.2));
    const scale = 1 + Math.sin(scroll / 360) * 0.018;

    ambientStage.style.setProperty('--watermark-y', `${parallaxY}px`);
    ambientStage.style.setProperty('--watermark-rotate', `${rotate.toFixed(2)}deg`);
    ambientStage.style.setProperty('--watermark-scale', scale.toFixed(3));
    ambientStage.style.setProperty('--watermark-opacity', '0.056');
  };

  const holdStackHeight = () => {
    const currentHeight = Math.ceil(stack.getBoundingClientRect().height);
    if (!currentHeight) return;

    window.clearTimeout(stackHeightTimer);
    stack.style.minHeight = `${currentHeight}px`;
    stackHeightTimer = window.setTimeout(() => {
      stack.style.minHeight = '';
    }, reducedMotion() ? 80 : 760);
  };

  const describeProduct = (product) => {
    if (product.sectionId === 'strong') return '';
    if (product.desc) return product.desc;
    if (product.sectionId === 'tea') return 'Чёрный или зелёный чай.';
    if (product.sectionId === 'sauces') return 'Порционный соус.';
    return '';
  };

  const getProducts = (section) => section.groups.flatMap((group) => {
    return (group.items || []).map((item) => {
      const price = item.price || sectionPriceFromNote(section);
      const groupTitle = group.title || section.label || section.title;
      let metaParts = [groupTitle];

      if (section.id === 'strong') {
        metaParts = [item.desc || section.note || '50 мл'];
      }

      if (section.id === 'wine') {
        metaParts = [item.desc || section.note || '150 мл'];
      }

      if (section.id === 'tea') {
        metaParts = ['чай', 'чёрный / зелёный'];
      }

      if (section.id === 'sauces') {
        metaParts = ['соус'];
      }

      const meta = metaParts.filter(Boolean).map(cleanTitle).join(' · ');

      return {
        ...item,
        price,
        sectionId: section.id,
        sectionTitle: section.title,
        theme: section.theme,
        groupTitle,
        meta
      };
    });
  });

  const getProductPhoto = (product) => versionedAsset(product.image || '');

  const productVariant = (product) => getProductPhoto(product) ? 'photo' : 'compact';

  const preloadImage = (src) => {
    const imageSrc = versionedAsset(src);
    if (!imageSrc || preloadedImages.has(imageSrc)) return;
    preloadedImages.add(imageSrc);
    const image = new Image();
    image.decoding = 'async';
    image.src = imageSrc;
  };

  const preloadProductImages = (products) => {
    products.map(getProductPhoto).filter(Boolean).forEach(preloadImage);
  };

  const warmMenuImages = () => {
    const run = () => {
      menuSections.forEach((section) => {
        section.groups?.forEach((group) => {
          group.items?.forEach((item) => preloadImage(item.image));
        });
      });
    };

    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(run, { timeout: 1200 });
      return;
    }

    window.setTimeout(run, 350);
  };

  const iconTypeForProduct = (product) => {
    const name = cleanTitle(product.name).toLowerCase();
    if (product.icon) return product.icon;
    if (product.sectionId === 'cocktails') return 'cocktail';
    if (product.sectionId === 'strong') return 'shot';
    if (product.sectionId === 'wine') return 'wine';
    if (product.sectionId === 'coffee') return 'coffee';
    if (product.sectionId === 'tea') return 'tea';
    if (product.sectionId === 'lemonades') return 'lemonade';
    if (product.sectionId === 'soups') return 'soup';
    if (product.sectionId === 'salads') return 'salad';
    if (product.sectionId === 'sauces') return 'sauce';
    if (product.sectionId === 'main') return name.includes('шаверма') || name.includes('кесадилья') ? 'wrap' : 'food';
    if (product.sectionId === 'soft') return name.includes('квас') ? 'bottle' : 'soft';
    if (product.sectionId === 'beer') return 'beer';
    return product.theme === 'food' ? 'food' : 'drink';
  };

  const renderProductMedia = (product, mode = 'tile', usePhoto = true) => {
    const src = getProductPhoto(product);
    if (src && usePhoto) {
      const className = mode === 'dialog' ? '' : 'product-tile-photo';
      const isPriority = mode === 'dialog' || product.lead;
      const loading = mode === 'tile' || isPriority ? 'eager' : 'lazy';
      const fetchPriority = isPriority ? 'high' : 'auto';
      return `<img class="${className}" src="${escapeHtml(src)}" width="480" height="360" alt="${escapeHtml(product.name)}" loading="${loading}" decoding="async" fetchpriority="${fetchPriority}">`;
    }

    const emptyClass = mode === 'dialog' ? 'dialog-media-empty' : 'product-tile-empty';
    return `
      <div class="${emptyClass}">
        ${productIcon(iconTypeForProduct(product))}
      </div>
    `;
  };

  const renderProductTile = (product, index, variant = productVariant(product), extraClass = '') => `
    <button class="product-tile product-tile--${variant}${extraClass ? ` ${extraClass}` : ''}" type="button" data-product-index="${index}" data-theme="${escapeHtml(product.theme)}" style="--index:${index}" aria-label="Открыть ${escapeHtml(productTitle(product))}">
      ${renderProductMedia(product, 'tile', variant === 'photo' || extraClass.includes('product-tile--compact-photo'))}
      <div class="product-tile-body">
        <h3>${escapeHtml(productTitle(product))}</h3>
        ${describeProduct(product) ? `<p class="product-tile-desc">${escapeHtml(describeProduct(product))}</p>` : ''}
      </div>
      <div class="product-tile-footer">
        <strong class="product-tile-price">${escapeHtml(product.price || '—')}</strong>
        <span class="product-tile-more" aria-hidden="true"></span>
      </div>
    </button>
  `;

  const renderSauceTile = (product, index) => `
    <button class="sauce-tile" type="button" data-product-index="${index}" style="--index:${index}">
      <span>${escapeHtml(productTitle(product))}</span>
      <strong>${escapeHtml(product.price || '')}</strong>
    </button>
  `;

  const renderProductCollection = (section) => {
    if (section.id === 'sauces') {
      return `<div class="sauce-board">${activeProducts.map(renderSauceTile).join('')}</div>`;
    }

    const sectionUsesLead = new Set(menuData.leadSections || []).has(section.id);
    const seenPhotos = new Set();
    const decoratedProducts = activeProducts.map((product, index) => {
      const src = getProductPhoto(product);
      const variant = src && !seenPhotos.has(src) ? 'photo' : 'compact';
      if (src) seenPhotos.add(src);
      return { product: variant === 'photo' ? product : { ...product, image: '' }, index, variant };
    });

    const explicitLeadIndex = decoratedProducts.findIndex(({ product }) => product.lead);
    const firstPhotoIndex = decoratedProducts.findIndex(({ variant }) => variant === 'photo');
    const leadIndex = sectionUsesLead && decoratedProducts.length
      ? (explicitLeadIndex >= 0 ? explicitLeadIndex : (firstPhotoIndex >= 0 ? firstPhotoIndex : 0))
      : -1;
    const leadProduct = leadIndex >= 0 ? decoratedProducts[leadIndex] : null;
    const restProducts = leadProduct ? decoratedProducts.filter((_, index) => index !== leadIndex) : decoratedProducts;
    const restPhotoProducts = restProducts.filter(({ variant }) => variant === 'photo');
    const useFeaturePhotoGrid = restPhotoProducts.length >= 3;
    const photoProducts = useFeaturePhotoGrid ? restPhotoProducts : [];
    const compactProducts = useFeaturePhotoGrid ? restProducts.filter(({ variant }) => variant !== 'photo') : restProducts;

    return `
      <div class="product-card-grid product-card-grid--${escapeHtml(section.theme)} product-card-grid--${escapeHtml(section.id)}">
        ${leadProduct ? `
          <div class="product-lead-grid">
            ${renderProductTile(
              leadProduct.product,
              leadProduct.index,
              getProductPhoto(leadProduct.product) ? 'photo' : 'compact',
              `product-tile--lead${getProductPhoto(leadProduct.product) ? '' : ' product-tile--lead-icon'}`
            )}
          </div>
        ` : ''}
        ${photoProducts.length ? `
          <div class="product-feature-grid">
            ${photoProducts.map(({ product, index, variant }) => renderProductTile(product, index, variant)).join('')}
          </div>
        ` : ''}
        ${compactProducts.length ? `
          <div class="product-compact-list">
            ${compactProducts.map(({ product, index, variant }) => {
              const compactVariant = variant === 'photo' ? 'compact' : variant;
              const compactClass = variant === 'photo' ? 'product-tile--compact-photo' : '';
              return renderProductTile(product, index, compactVariant, compactClass);
            }).join('')}
          </div>
        ` : ''}
      </div>
    `;
  };

  const openProduct = (index) => {
    const product = activeProducts[index];
    if (!product) return;

    dialog.dataset.theme = product.theme;
    dialogMedia.innerHTML = renderProductMedia(product, 'dialog');
    dialogMeta.hidden = !product.meta;
    dialogMeta.textContent = product.meta || '';
    dialogTitle.textContent = productTitle(product);
    dialogDescription.hidden = true;
    dialogDescription.textContent = '';
    const details = describeProduct(product);
    dialogLabel.hidden = !details;
    dialogComposition.hidden = !details;
    dialogComposition.textContent = details;
    dialogPrice.textContent = product.price || '';

    if (dialog.showModal) {
      dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
  };

  const closeProduct = () => {
    if (dialog.close) {
      dialog.close();
    } else {
      dialog.removeAttribute('open');
    }
  };

  const renderSection = (id, options = {}) => {
    const section = sectionById.get(id) || menuSections[0];
    if (!section) return;
    const shouldScroll = Boolean(options.scroll);
    if (shouldScroll) holdStackHeight();

    activeProducts = getProducts(section);
    preloadProductImages(activeProducts);
    const displayNote = sectionDisplayNote(section);
    boardTitle.textContent = section.title;
    board.dataset.theme = section.theme;
    document.body.dataset.activeTheme = section.theme;
    document.body.dataset.activeSection = section.id;

    const mountSection = () => {
      stack.innerHTML = `
        <section class="active-menu-section active-menu-section--${escapeHtml(section.theme)}" id="${escapeHtml(section.id)}" data-section="${escapeHtml(section.id)}" aria-labelledby="menu-board-title">
          <div class="active-section-body">
            ${displayNote ? `
            <div class="section-info-row">
              <p class="active-section-note">${escapeHtml(displayNote)}</p>
            </div>
            ` : ''}
            ${renderProductCollection(section)}
          </div>
        </section>
      `;

      const mountedSection = stack.querySelector('.active-menu-section');
      requestAnimationFrame(() => mountedSection?.classList.add('is-mounted'));

      stack.querySelectorAll('[data-product-index]').forEach((tile) => {
        tile.addEventListener('click', () => openProduct(Number(tile.dataset.productIndex)));
      });

      if (shouldScroll) {
        requestAnimationFrame(() => scrollToBoardStart());
        window.clearTimeout(stackHeightTimer);
        stackHeightTimer = window.setTimeout(() => {
          stack.style.minHeight = '';
        }, reducedMotion() ? 120 : 720);
      }
    };

    window.clearTimeout(renderTimer);
    const currentSection = stack.querySelector('.active-menu-section');
    if (currentSection && !reducedMotion()) {
      currentSection.classList.remove('is-mounted');
      currentSection.classList.add('is-leaving');
      renderTimer = window.setTimeout(mountSection, 150);
    } else {
      mountSection();
    }

    setActive(section.id);
    requestAnimationFrame(syncWatermarkMotion);
    if (options.updateUrl !== false) {
      history.replaceState(null, '', `#${section.id}`);
    }
  };

  const syncScrollState = () => {
    scrollTicking = false;
    document.body.classList.toggle('is-scrolled', window.scrollY > 8);
    syncWatermarkMotion();
  };

  const init = async () => {
    menuData = await loadMenuData();
    menuSections = menuData.sections || [];
    sectionById = new Map(menuSections.map((section) => [section.id, section]));

    renderBrand();
    renderNav();

    window.addEventListener('scroll', () => {
      if (scrollTicking) return;
      scrollTicking = true;
      requestAnimationFrame(syncScrollState);
    }, { passive: true });
    window.addEventListener('resize', () => requestAnimationFrame(() => {
      syncCategoryMarker();
      syncWatermarkMotion();
    }), { passive: true });
    syncScrollState();

    dialogClose.addEventListener('click', closeProduct);
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) closeProduct();
    });

    const initialId = location.hash.replace('#', '') || menuData.navigation?.initialSection || 'beer';
    renderSection(sectionById.has(initialId) ? initialId : (menuData.navigation?.initialSection || 'beer'), { updateUrl: Boolean(location.hash) });
    warmMenuImages();
  };

  init().catch((error) => {
    console.error('Failed to initialize Iliamo menu:', error);
    stack.innerHTML = '<p class="load-error">Не удалось загрузить меню.</p>';
  });
})();
