/** Comments on one video (SPEC §8.11, Tier 2): newest first, ≤ 300 characters,
 * delete your own, report anyone else's. Three reports hide a comment. */
import { useEffect, useState } from 'react';

import { api, ApiError } from '../lib/api';
import { useApp } from '../lib/app-state';
import { date } from '../lib/format';
import type { CommentItem } from '../lib/types';
import { BottomSheet } from './common';
import { Icon } from './Icon';

const MAX = 300;

export function CommentsSheet({ mediaId, onClose }: { mediaId: number; onClose: () => void }) {
  const { me, toast } = useApp();
  const [comments, setComments] = useState<CommentItem[] | null>(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .comments(mediaId)
      .then((response) => !cancelled && setComments(response.comments))
      .catch(() => !cancelled && setComments([]));
    return () => {
      cancelled = true;
    };
  }, [mediaId]);

  function fail(error: unknown) {
    toast(error instanceof ApiError ? error.message : 'That did not work.', 'bad');
  }

  async function post() {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const comment = await api.addComment(mediaId, text);
      setComments((list) => [comment, ...(list ?? [])]);
      setText('');
    } catch (error) {
      fail(error);
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteComment(id);
      setComments((list) => (list ?? []).filter((c) => c.id !== id));
    } catch (error) {
      fail(error);
    }
  }

  async function report(id: number) {
    try {
      const result = await api.report('comment', id, 'offensive');
      if (result.hidden) setComments((list) => (list ?? []).filter((c) => c.id !== id));
      toast('Reported. Thank you.', 'plain');
    } catch (error) {
      fail(error);
    }
  }

  return (
    <BottomSheet open onClose={onClose} title="Comments" className="comments-sheet">
      {comments === null ? (
        <p className="c-muted">Loading…</p>
      ) : comments.length === 0 ? (
        <p className="c-muted">No comments yet. Been here? Say how it was.</p>
      ) : (
        <ul className="comment-list">
          {comments.map((c) => (
            <li key={c.id} className="comment">
              <div className="comment-head">
                <b>@{c.user.username}</b>
                <span className="c-muted">{date(c.at)}</span>
              </div>
              <p>{c.text}</p>
              {c.mine ? (
                <button type="button" className="btn btn-text btn-sm" onClick={() => void remove(c.id)}>
                  <Icon name="i-trash" size={15} /> Delete
                </button>
              ) : (
                me && (
                  <button type="button" className="btn btn-text btn-sm" onClick={() => void report(c.id)}>
                    <Icon name="i-flag" size={15} /> Report
                  </button>
                )
              )}
            </li>
          ))}
        </ul>
      )}

      {me ? (
        <form
          className="comment-form"
          onSubmit={(event) => {
            event.preventDefault();
            void post();
          }}
        >
          <label className="sr-only" htmlFor="comment-text">
            Add a comment
          </label>
          <textarea
            id="comment-text"
            rows={2}
            maxLength={MAX}
            value={text}
            placeholder="Add a comment"
            onChange={(event) => setText(event.target.value)}
          />
          <div className="comment-actions">
            <span className="c-muted">
              {text.length} / {MAX}
            </span>
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !text.trim()}>
              Post
            </button>
          </div>
        </form>
      ) : (
        <p className="c-muted">Sign in to comment.</p>
      )}
    </BottomSheet>
  );
}
