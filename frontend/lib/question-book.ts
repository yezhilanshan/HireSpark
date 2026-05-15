'use client'

export type BookMarkType = 'favorite' | 'mistake' | 'review'

export type QuestionBookItem = {
    questionId: string
    questionTitle: string
    category: string
    roundType: string
    difficulty: string
    positionKey: string
    bookmarkedAt: number
    type: BookMarkType
}

export type DiscussionItem = {
    id: string
    questionId: string
    author: string
    avatar: string
    content: string
    likes: number
    isOfficial: boolean
    createdAt: number
}

const BOOKMARK_KEY = 'zhiyuexingchen.question.bookmarks.v1'
const DISCUSSION_KEY = 'zhiyuexingchen.question.discussions.v1'

function readBookmarks(): QuestionBookItem[] {
    try {
        const raw = localStorage.getItem(BOOKMARK_KEY)
        if (!raw) return []
        const parsed = JSON.parse(raw)
        return Array.isArray(parsed) ? parsed : []
    } catch {
        return []
    }
}

function writeBookmarks(items: QuestionBookItem[]) {
    try {
        localStorage.setItem(BOOKMARK_KEY, JSON.stringify(items))
    } catch {
        // ignore
    }
}

export function getBookmarks(): QuestionBookItem[] {
    return readBookmarks()
}

export function addBookmark(
    questionId: string,
    questionTitle: string,
    category: string,
    roundType: string,
    difficulty: string,
    positionKey: string,
    type: BookMarkType = 'favorite'
) {
    const items = readBookmarks()
    const exists = items.some(
        (item) => item.questionId === questionId && item.type === type
    )
    if (exists) return false

    items.push({
        questionId,
        questionTitle,
        category,
        roundType,
        difficulty,
        positionKey,
        bookmarkedAt: Date.now(),
        type,
    })
    writeBookmarks(items)
    return true
}

export function removeBookmark(questionId: string, type?: BookMarkType) {
    const items = readBookmarks()
    const next = items.filter(
        (item) =>
            item.questionId !== questionId ||
            (type !== undefined && item.type !== type)
    )
    writeBookmarks(next)
}

export function toggleBookmark(
    questionId: string,
    questionTitle: string,
    category: string,
    roundType: string,
    difficulty: string,
    positionKey: string,
    type: BookMarkType = 'favorite'
) {
    const items = readBookmarks()
    const exists = items.some(
        (item) => item.questionId === questionId && item.type === type
    )
    if (exists) {
        removeBookmark(questionId, type)
        return false
    }
    addBookmark(questionId, questionTitle, category, roundType, difficulty, positionKey, type)
    return true
}

export function isBookmarked(questionId: string, type?: BookMarkType): boolean {
    const items = readBookmarks()
    if (type) {
        return items.some((item) => item.questionId === questionId && item.type === type)
    }
    return items.some((item) => item.questionId === questionId)
}

export function getBookmarksByType(type: BookMarkType): QuestionBookItem[] {
    return readBookmarks()
        .filter((item) => item.type === type)
        .sort((a, b) => b.bookmarkedAt - a.bookmarkedAt)
}

export function getBookmarkTypesForQuestion(questionId: string): BookMarkType[] {
    return readBookmarks()
        .filter((item) => item.questionId === questionId)
        .map((item) => item.type)
}

// Discussions
function readDiscussions(): DiscussionItem[] {
    try {
        const raw = localStorage.getItem(DISCUSSION_KEY)
        if (!raw) return []
        const parsed = JSON.parse(raw)
        return Array.isArray(parsed) ? parsed : []
    } catch {
        return []
    }
}

function writeDiscussions(items: DiscussionItem[]) {
    try {
        localStorage.setItem(DISCUSSION_KEY, JSON.stringify(items))
    } catch {
        // ignore
    }
}

export function getDiscussionsForQuestion(questionId: string): DiscussionItem[] {
    return readDiscussions()
        .filter((item) => item.questionId === questionId)
        .sort((a, b) => b.createdAt - a.createdAt)
}

export function addDiscussion(
    questionId: string,
    author: string,
    avatar: string,
    content: string,
    isOfficial = false
): DiscussionItem {
    const items = readDiscussions()
    const newItem: DiscussionItem = {
        id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        questionId,
        author,
        avatar,
        content,
        likes: 0,
        isOfficial,
        createdAt: Date.now(),
    }
    items.push(newItem)
    writeDiscussions(items)
    return newItem
}

export function likeDiscussion(discussionId: string) {
    const items = readDiscussions()
    const item = items.find((i) => i.id === discussionId)
    if (item) {
        item.likes += 1
        writeDiscussions(items)
    }
}

export function getAllDiscussions(): DiscussionItem[] {
    return readDiscussions().sort((a, b) => b.createdAt - a.createdAt)
}
