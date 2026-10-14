/**
 * Slide viewer for decks exported from PowerPoint.
 *
 * Each talk page sets window.DECK before loading this file:
 *   { title, pdf, aspect, count,
 *     media: { "<slide>": [{ kind: "video" | "loop" | "image", src, box: [x, y, w, h] }] } }
 * Slides are slides/001.webp, 002.webp, ...; thumbnails are thumbs/001.webp, ...
 * `box` is the figure's place on the slide as fractions of its width and height.
 *
 * Keys: arrows, space, PageUp/PageDown, Home/End to move; o overview; f fullscreen.
 */
(() => {
  const D = window.DECK
  const N = D.count
  const pad = n => String(n).padStart(3, '0')
  const slideSrc = n => `slides/${pad(n)}.webp`
  const thumbSrc = n => `thumbs/${pad(n)}.webp`
  const icon = d => `<svg viewBox="0 0 24 24" aria-hidden="true">${d}</svg>`

  document.documentElement.style.setProperty('--aspect', D.aspect)
  document.body.innerHTML = `
    <div class="dk-stage" aria-live="polite">
      <div class="dk-slide"><img class="dk-img" alt=""><div class="dk-media"></div></div>
    </div>
    <div class="dk-overview" hidden><h1></h1><div class="dk-grid"></div></div>
    <nav class="dk-bar" aria-label="Slide controls">
      <a href="../" title="All talks">${icon('<path d="M3 11l9-8 9 8"/><path d="M5 9.5V20h14V9.5"/>')}<span class="dk-label">All talks</span></a>
      <span class="dk-title"></span>
      <span class="dk-sep"></span>
      <button data-act="prev" title="Previous (←)" aria-label="Previous slide">${icon('<path d="M15 18l-6-6 6-6"/>')}</button>
      <span class="dk-count"></span>
      <button data-act="next" title="Next (→)" aria-label="Next slide">${icon('<path d="M9 18l6-6-6-6"/>')}</button>
      <span class="dk-sep"></span>
      <button data-act="overview" title="Overview (o)" aria-label="Slide overview">${icon('<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>')}</button>
      <button data-act="fullscreen" title="Fullscreen (f)" aria-label="Fullscreen">${icon('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>')}</button>
      ${D.pdf ? `<a class="dk-pdf" href="${D.pdf}" download title="Download PDF">${icon('<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>')}PDF</a>` : ''}
    </nav>`

  const $ = s => document.querySelector(s)
  const stage = $('.dk-stage'), img = $('.dk-img'), layer = $('.dk-media')
  const count = $('.dk-count'), overview = $('.dk-overview'), grid = $('.dk-grid')
  $('.dk-title').textContent = D.title
  overview.querySelector('h1').textContent = D.title
  document.title = D.title

  let cur = 0

  function placeMedia(n) {
    for (const el of layer.querySelectorAll('video')) el.pause()
    layer.replaceChildren()
    for (const m of (D.media && D.media[n]) || []) {
      let el
      if (m.kind === 'image') {
        el = document.createElement('img')
        el.alt = ''
      }
      else {
        el = document.createElement('video')
        el.muted = true
        el.playsInline = true
        el.preload = 'auto'
        if (m.kind === 'loop') { el.loop = true; el.autoplay = true }
        else el.controls = true
      }
      el.src = m.src
      const [x, y, w, h] = m.box
      Object.assign(el.style, { left: `${x * 100}%`, top: `${y * 100}%`, width: `${w * 100}%`, height: `${h * 100}%` })
      layer.appendChild(el)
      if (el.tagName === 'VIDEO') el.play().catch(() => {})
    }
  }

  function go(n, { push = false } = {}) {
    n = Math.min(N, Math.max(1, n | 0))
    if (n === cur) return
    cur = n
    img.src = slideSrc(n)
    img.alt = `Slide ${n} of ${N}`
    count.textContent = `${n} / ${N}`
    placeMedia(n)
    const hash = `#${n}`
    if (location.hash !== hash) history[push ? 'pushState' : 'replaceState'](null, '', hash)
    for (const k of [n + 1, n - 1]) if (k >= 1 && k <= N) new Image().src = slideSrc(k)
  }

  const next = () => go(cur + 1)
  const prev = () => go(cur - 1)

  function toggleOverview(show = overview.hidden) {
    overview.hidden = !show
    if (!show) return
    if (!grid.childElementCount) {
      for (let i = 1; i <= N; i++) {
        const b = document.createElement('button')
        b.dataset.n = i
        b.setAttribute('aria-label', `Go to slide ${i}`)
        b.innerHTML = `<img loading="lazy" alt="" src="${thumbSrc(i)}"><span>${i}</span>`
        grid.appendChild(b)
      }
    }
    for (const b of grid.children) b.classList.toggle('current', +b.dataset.n === cur)
    const c = grid.querySelector('.current')
    if (c) { c.scrollIntoView({ block: 'center' }); c.focus({ preventScroll: true }) }
  }

  function toggleFullscreen() {
    const el = document.documentElement
    if (document.fullscreenElement || document.webkitFullscreenElement)
      (document.exitFullscreen || document.webkitExitFullscreen).call(document)
    else (el.requestFullscreen || el.webkitRequestFullscreen)?.call(el)
  }
  if (!(document.documentElement.requestFullscreen || document.documentElement.webkitRequestFullscreen))
    $('[data-act="fullscreen"]').remove()

  grid.addEventListener('click', e => {
    const b = e.target.closest('button')
    if (b) { go(+b.dataset.n); toggleOverview(false) }
  })
  $('.dk-bar').addEventListener('click', e => {
    const act = e.target.closest('button')?.dataset.act
    if (act === 'prev') prev()
    else if (act === 'next') next()
    else if (act === 'overview') toggleOverview()
    else if (act === 'fullscreen') toggleFullscreen()
  })

  // Click the left third to go back, anywhere else to go forward.
  // Clicks on a video or figure stay with it.
  stage.addEventListener('click', e => {
    if (e.target.closest('.dk-media > *')) return
    const r = stage.getBoundingClientRect()
    e.clientX - r.left < r.width / 3 ? prev() : next()
  })

  let touch = null
  stage.addEventListener('touchstart', e => { touch = e.touches.length === 1 ? e.touches[0] : null }, { passive: true })
  stage.addEventListener('touchend', e => {
    if (!touch) return
    const t = e.changedTouches[0], dx = t.clientX - touch.clientX, dy = t.clientY - touch.clientY
    touch = null
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) { e.preventDefault(); dx < 0 ? next() : prev() }
  })

  document.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return
    if (e.target.closest('video')) return
    const k = e.key
    if (!overview.hidden) {
      if (k === 'Escape' || k === 'o') { e.preventDefault(); toggleOverview(false) }
      return
    }
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter', 'n'].includes(k)) next()
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace', 'p'].includes(k)) prev()
    else if (k === 'Home') go(1)
    else if (k === 'End') go(N)
    else if (k === 'o') toggleOverview(true)
    else if (k === 'f') toggleFullscreen()
    else return
    e.preventDefault()
  })

  // Hide the control bar while the mouse rests, so the slide is clean when presenting.
  let idle
  const wake = () => {
    document.body.classList.remove('dk-idle')
    clearTimeout(idle)
    idle = setTimeout(() => document.body.classList.add('dk-idle'), 2500)
  }
  document.addEventListener('mousemove', wake)
  wake()

  const fromHash = () => parseInt(location.hash.slice(1), 10) || 1
  window.addEventListener('hashchange', () => go(fromHash()))
  go(fromHash())
})()
